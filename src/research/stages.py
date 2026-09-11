"""Stage implementations. Each stage reads its inputs from files and returns its outputs."""
from __future__ import annotations

import pandas as pd

from .artifacts import PROCESSED_FILES, read_table, run_path
from .audit import audit_site
from .config import inferential
from .crawl import load_crawl
from .data import DataError, available_until, load_tables, normalized_gsc, validate_snapshot
from .design import build_design, ctr_training_end
from .estimate import (PREDICTION_KEY, build_predictions, compute_page_windows, evaluate, fit_ctr_curve,
                       models_for)
from .io_utils import read_json, read_sha256sums, sha256_file, tree_sha256, write_csv, write_json

ABLATION_MODELS = ("did", "naive_prepost", "did_raw_ctr")


def stage_ingest(ctx):
    tree, files = tree_sha256(ctx.snapshot_dir)
    sums = ctx.snapshot_dir / "SHA256SUMS"
    declared = read_sha256sums(sums) if sums.is_file() else {}
    out = ctx.run_dir / "stages" / "ingest" / "snapshot.json"
    write_json(out, {"snapshot": ctx.rel(ctx.snapshot_dir), "tree_sha256": tree, "files": files,
                     "sha256sums_match": declared == files})
    if tree != ctx.manifest["data_sha256"]:
        raise DataError("snapshot content differs from data_sha256 recorded at run creation")
    if declared != files:
        raise DataError("SHA256SUMS does not match the snapshot files")
    return [out]


def stage_validate(ctx):
    issues = validate_snapshot(ctx.snapshot_dir, ctx.config)
    errors = [i for i in issues if i["severity"] == "error"]
    out = ctx.run_dir / "stages" / "validate" / "validation.json"
    write_json(out, {"passed": not errors, "errors": errors,
                     "warnings": [i for i in issues if i["severity"] != "error"]})
    if errors:
        raise DataError(f"{len(errors)} validation errors; first: {errors[0]}")
    return [out]


def stage_transform(ctx):
    out_dir = ctx.processed_dir
    provenance = out_dir / "PROVENANCE.json"
    outputs = [out_dir / name for name in PROCESSED_FILES] + [provenance]
    if provenance.is_file():
        record = read_json(provenance)
        if (record.get("data_sha256") == ctx.manifest["data_sha256"]
                and record.get("source_bundle_sha256") == ctx.manifest["source_bundle_sha256"]
                and set(record.get("files", {})) == set(PROCESSED_FILES)
                and all((out_dir / n).is_file() and sha256_file(out_dir / n) == s
                        for n, s in record["files"].items())):
            ctx.log("[transform] processed files match their provenance, reused")
            return outputs
        ctx.log("[transform] processed files are stale or damaged, rebuilding")
        provenance.unlink()

    tables = load_tables(ctx.snapshot_dir)
    segment, page = normalized_gsc(tables)
    write_csv(out_dir / "panel_segment_day.csv", segment)
    write_csv(out_dir / "panel_page_day.csv", page)
    url_to_page = dict(zip(tables["pages.csv"]["url"], tables["pages.csv"]["page"]))
    for label in ("before", "after"):
        facts, issues = audit_site(load_crawl(ctx.snapshot_dir / "crawl" / label))
        for frame in (facts, issues):
            if not frame.empty:
                frame.insert(0, "page", frame["url"].map(url_to_page).fillna(""))
        write_csv(out_dir / f"audit_pages_{label}.csv", facts)
        write_csv(out_dir / f"audit_issues_{label}.csv", issues)
    write_json(provenance, {"data_sha256": ctx.manifest["data_sha256"],
                            "source_bundle_sha256": ctx.manifest["source_bundle_sha256"],
                            "files": {name: sha256_file(out_dir / name) for name in PROCESSED_FILES}})
    return outputs


def stage_split(ctx):
    tables = load_tables(ctx.snapshot_dir)
    pages, interventions = tables["pages.csv"], tables["interventions.csv"]
    design = write_csv(run_path(ctx.run_dir, "design"), build_design(ctx.config, pages, interventions))
    placebo = write_csv(run_path(ctx.run_dir, "placebo_design"),
                        build_design(ctx.config, pages, interventions,
                                     placebo_shift_days=ctx.config["design"]["placebo_shift_days"]))
    ctx.manifest["split_sha256"] = sha256_file(design)
    return [design, placebo]


def _panels(ctx):
    return (read_table(ctx.processed_dir / "panel_page_day.csv"),
            read_table(ctx.processed_dir / "panel_segment_day.csv"))


def stage_fit(ctx):
    tables = load_tables(ctx.snapshot_dir)
    panel_page, _ = _panels(ctx)
    curve = fit_ctr_curve(panel_page, ctr_training_end(tables["interventions.csv"], ctx.config),
                          available_until(ctx.config))
    return [write_json(run_path(ctx.run_dir, "curve"), curve)]


def _predict(ctx, design, run_id):
    panel_page, panel_segment = _panels(ctx)
    curve = read_json(run_path(ctx.run_dir, "curve"))
    page_windows = compute_page_windows(ctx.config, design, panel_page, panel_segment, curve)
    return page_windows, curve


def stage_predict(ctx):
    design = read_table(run_path(ctx.run_dir, "design"))
    page_windows, _ = _predict(ctx, design, ctx.run_id)
    frames = [build_predictions(ctx.config, hyp, page_windows, design, model, ctx.run_id)
              for hyp in inferential(ctx.config) for model in models_for(hyp)]
    predictions = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not predictions.empty and predictions.duplicated(PREDICTION_KEY).any():
        raise RuntimeError("duplicate prediction keys")
    return [write_csv(run_path(ctx.run_dir, "page_windows"), page_windows),
            write_csv(run_path(ctx.run_dir, "predictions"), predictions)]


def _evaluation_inputs(ctx, prefix=""):
    return (read_table(run_path(ctx.run_dir, f"{prefix}page_windows")),
            read_table(run_path(ctx.run_dir, f"{prefix}predictions")),
            load_tables(ctx.snapshot_dir))


def stage_evaluate(ctx):
    page_windows, predictions, tables = _evaluation_inputs(ctx)
    metrics = evaluate(ctx.config, page_windows, predictions, tables, ctx.run_id, ("did",),
                       available_until(ctx.config))
    return [write_csv(run_path(ctx.run_dir, "metrics"), metrics)]


def stage_diagnostics(ctx):
    page_windows, predictions, tables = _evaluation_inputs(ctx)
    avail = available_until(ctx.config)
    ablation = evaluate(ctx.config, page_windows, predictions, tables, ctx.run_id, ABLATION_MODELS, avail)
    ablation = ablation[ablation["kind"] != "descriptive"]

    design = read_table(run_path(ctx.run_dir, "placebo_design"))
    placebo_windows, _ = _predict(ctx, design, ctx.run_id)
    frames = [build_predictions(ctx.config, hyp, placebo_windows, design, "did", ctx.run_id)
              for hyp in inferential(ctx.config)]
    placebo_predictions = pd.concat(frames, ignore_index=True)
    placebo = evaluate(ctx.config, placebo_windows, placebo_predictions, tables, ctx.run_id, ("did",), avail,
                       tag="placebo")
    placebo = placebo[placebo["kind"] != "descriptive"].copy()
    placebo["contains_zero"] = (placebo["ci_low"] <= 0) & (placebo["ci_high"] >= 0)
    return [write_csv(run_path(ctx.run_dir, "ablation"), ablation),
            write_csv(run_path(ctx.run_dir, "placebo"), placebo),
            write_csv(run_path(ctx.run_dir, "placebo_page_windows"), placebo_windows),
            write_csv(run_path(ctx.run_dir, "placebo_predictions"), placebo_predictions)]


def stage_report(ctx):
    from .report import build_report

    return build_report(ctx)


STAGES = [
    ("ingest", [], stage_ingest),
    ("validate", ["ingest"], stage_validate),
    ("transform", ["validate"], stage_transform),
    ("split", ["transform"], stage_split),
    ("fit", ["split"], stage_fit),
    ("predict", ["fit"], stage_predict),
    ("evaluate", ["predict"], stage_evaluate),
    ("diagnostics", ["predict"], stage_diagnostics),
    ("report", ["evaluate", "diagnostics"], stage_report),
]
