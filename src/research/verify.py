"""Independent checks of a finished run: completeness, hashes, provenance and metrics."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from .artifacts import read_table, run_path
from .config import STAGE_NAMES, config_sha256
from .data import available_until, load_tables
from .estimate import PREDICTION_KEY, describe_authority, model_metric, point_effect
from .io_utils import read_json, sha256_file, tree_sha256
from .manifest import utc_now
from .pipeline import environment_facts, source_bundle_sha256

TOLERANCE = 1e-9


def _recompute(frame, predictions, hypotheses, bad, label):
    for row in frame[frame["status"] == "estimated"].itertuples():
        hyp = hypotheses[row.hypothesis_id]
        selected = predictions[(predictions["hypothesis_id"] == row.hypothesis_id)
                               & (predictions["model"] == row.model)]
        value = point_effect(hyp, selected, model_metric(hyp, row.model)) if len(selected) else float("nan")
        if not abs(value - row.estimate) <= TOLERANCE:
            bad.append(f"{label}:{row.hypothesis_id}/{row.model} stored={row.estimate} recomputed={value}")


def verify_run(ctx) -> dict:
    manifest, cfg, run_dir = ctx.manifest, ctx.config, ctx.run_dir
    checks = []

    def check(name, ok, failure="", success=""):
        checks.append({"name": name, "ok": bool(ok), "detail": success if ok else failure})

    check("manifest_schema", manifest.get("schema_version") == 1 and manifest.get("run_id") == ctx.run_id)
    required = cfg.get("required_stages", list(STAGE_NAMES))
    unfinished = [s for s in required if manifest["stages"].get(s, {}).get("status") != "succeeded"]
    check("required_stages_succeeded", not unfinished, f"not succeeded: {unfinished}" if unfinished else "")

    recorded = {p: s for rec in manifest["stages"].values() if rec.get("status") == "succeeded"
                for p, s in (rec.get("outputs") or {}).items()}
    damaged = [p for p, s in recorded.items() if not ctx.resolve(p).is_file() or sha256_file(ctx.resolve(p)) != s]
    check("artifact_hashes", not damaged, f"missing or changed: {damaged[:5]}" if damaged else f"{len(recorded)} files")
    listed = {a["path"]: a["sha256"] for a in manifest.get("artifacts", [])}
    check("artifacts_listed", listed == recorded, "manifest.artifacts differs from stage outputs" if listed != recorded else "")

    snapshot = ctx.snapshot_dir
    check("data_sha256", snapshot.is_dir() and tree_sha256(snapshot)[0] == manifest["data_sha256"],
          "snapshot differs from the recorded data hash")
    check("config_sha256", config_sha256(cfg) == manifest["config_sha256"])
    check("source_bundle_sha256", source_bundle_sha256() == manifest["source_bundle_sha256"],
          "code changed after the run; use resume before verify")
    check("environment_sha256", environment_facts()[1] == manifest["environment_sha256"],
          "environment differs from the run environment")

    if unfinished or damaged:
        check("content_checks", False, "skipped because stages are unfinished or artefacts are missing")
        return _finish(ctx, checks)

    design_path = run_path(run_dir, "design")
    check("split_sha256", sha256_file(design_path) == manifest.get("split_sha256"))
    design = read_table(design_path)
    predictions = read_table(run_path(run_dir, "predictions"))
    metrics = read_table(run_path(run_dir, "metrics"))
    ablation = read_table(run_path(run_dir, "ablation"))
    placebo = read_table(run_path(run_dir, "placebo"))
    placebo_predictions = read_table(run_path(run_dir, "placebo_predictions"))
    hypotheses = {h["id"]: h for h in cfg["hypotheses"]}
    avail = available_until(cfg)

    check("prediction_run_id", predictions["run_id"].eq(ctx.run_id).all())
    duplicates = int(predictions.duplicated(PREDICTION_KEY).sum())
    check("prediction_keys_unique", duplicates == 0, f"{duplicates} duplicated keys")
    latest_end = (date.fromisoformat(avail) + timedelta(days=1)).isoformat()
    check("labels_available_at_cutoff",
          predictions["target_end"].le(latest_end).all() and predictions["label_cutoff"].eq(avail).all()
          and design.loc[design["period"] == "post", "end"].le(latest_end).all(),
          f"all target windows end on or before {avail}")
    pre = design[design["period"] == "pre"]
    buffer = cfg["design"]["buffer_days"]
    limits = pre["intervention_date"].map(lambda d: (date.fromisoformat(d) - timedelta(days=buffer)).isoformat())
    check("pre_windows_before_intervention", pre["end"].le(limits).all())
    overlap = []
    for (hid, arm, key), group in design.groupby(["hypothesis_id", "arm", "window_key"]):
        both = set(group.loc[group["role"] == "treated", "page"]) & set(group.loc[group["role"] == "control", "page"])
        if both:
            overlap.append(f"{hid}/{arm}/{key}: {sorted(both)}")
    check("treated_control_disjoint", not overlap, "; ".join(overlap))

    coverage = []
    for hid, group in predictions.groupby("hypothesis_id"):
        sets = {m: set(map(tuple, g[["arm", "window_key", "page"]].to_numpy())) for m, g in group.groupby("model")}
        if len({frozenset(s) for s in sets.values()}) > 1:
            coverage.append(hid)
    check("equal_model_coverage", not coverage, f"differs for {coverage}" if coverage else "")

    bad = []
    _recompute(metrics, predictions, hypotheses, bad, "metrics")
    _recompute(ablation, predictions, hypotheses, bad, "ablation")
    _recompute(placebo, placebo_predictions, hypotheses, bad, "placebo")
    tables = load_tables(snapshot)
    for row in metrics[metrics["kind"] == "descriptive"].itertuples():
        value = describe_authority(cfg, hypotheses[row.hypothesis_id], tables["authority.csv"],
                                   tables["interventions.csv"], avail)["estimate"]
        if not abs(value - row.estimate) <= TOLERANCE:
            bad.append(f"descriptive:{row.hypothesis_id}")
    check("metrics_recomputed_from_predictions", not bad, "; ".join(bad[:5]))

    reference = ablation[ablation["model"] == "did"].set_index("hypothesis_id")
    main = metrics[metrics["model"] == "did"].set_index("hypothesis_id")
    columns = ["estimate", "ci_low", "ci_high", "ci_low_adj", "ci_high_adj"]
    same = reference.index.equals(main.index) and ((reference[columns] - main[columns]).abs().fillna(0) <= TOLERANCE).all().all()
    check("ablation_reference_matches_metrics", same)

    report_dir = run_path(run_dir, "report")
    claims = read_table(report_dir / "claims.csv")
    claim_problems = []
    indexed = metrics.set_index(["hypothesis_id", "model"])
    for claim in claims.itertuples():
        if claim.run_id != ctx.run_id or not (run_dir / claim.file).is_file():
            claim_problems.append(f"{claim.claim_id}: wrong run or missing file")
            continue
        if claim.file == "metrics/metrics.csv":
            hid = claim.claim_id.removeprefix("C-")
            stored = indexed.loc[(hid, "did" if hypotheses[hid]["kind"] != "descriptive" else "descriptive"), "estimate"]
            if not abs(stored - claim.value) <= TOLERANCE:
                claim_problems.append(f"{claim.claim_id}: {claim.value} != {stored}")
        elif claim.claim_id == "C-AUDIT":
            audit = read_table(report_dir / "tables" / "audit_summary.csv")
            if float(audit["before"].sum()) != float(claim.value):
                claim_problems.append("C-AUDIT")
    check("claims_match_run", not claim_problems, "; ".join(claim_problems))

    site = read_json(report_dir / "site_data.json")
    export_problems = []
    for item in site["hypotheses"]:
        stored = main.loc[item["hypothesis_id"]] if item["hypothesis_id"] in main.index else \
            metrics[metrics["hypothesis_id"] == item["hypothesis_id"]].iloc[0]
        for column in ("estimate", "ci_low_adj", "ci_high_adj"):
            left, right = item.get(column), stored.get(column)
            if (left is None) != pd.isna(right) or (left is not None and abs(left - right) > TOLERANCE):
                export_problems.append(f"{item['hypothesis_id']}.{column}")
        if item["decision"] != stored["decision"]:
            export_problems.append(f"{item['hypothesis_id']}.decision")
    check("site_export_matches_metrics", site["run_id"] == ctx.run_id and not export_problems,
          "; ".join(export_problems))
    return _finish(ctx, checks)


def _finish(ctx, checks) -> dict:
    result = {"status": "passed" if all(c["ok"] for c in checks) else "failed",
              "checked_at_utc": utc_now(), "checks": checks}
    ctx.manifest["verification"] = result
    ctx.save()
    return result
