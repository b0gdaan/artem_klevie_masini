"""Integration tests: determinism, interruption, failures, cache invalidation and verification."""
import shutil

import pandas as pd

from conftest import ROOT, SMOKE_CONFIG, SMOKE_SNAPSHOT, run_smoke
from research import cli
from research.artifacts import read_table, run_path
from research.io_utils import atomic_write_text, format_sha256sums, sha256_file, tree_sha256, write_csv
from research.manifest import load_manifest
from research.pipeline import execute, open_run, refresh_facts
from research.release import release_run
from research.verify import verify_run

COMPARED = ["page_windows", "predictions", "metrics", "ablation", "placebo", "placebo_predictions"]
UP_TO_TRANSFORM = ["ingest", "validate", "transform"]
CLEAN_JUNIT = ('<testsuites><testsuite name="s" tests="1" failures="0" errors="0" skipped="0">'
               '<testcase name="a"/></testsuite></testsuites>')


def _table(ctx, name):
    frame = read_table(run_path(ctx.run_dir, name))
    return frame.drop(columns=[c for c in ("run_id",) if c in frame.columns])


def _snapshot_copy(tmp_path):
    snapshot = tmp_path / "snapshot"
    shutil.copytree(SMOKE_SNAPSHOT, snapshot)
    return snapshot


def _reseal(snapshot):
    atomic_write_text(snapshot / "SHA256SUMS", format_sha256sums(tree_sha256(snapshot)[1]))


def _log(ctx):
    return (ctx.run_dir / "logs" / "run.log").read_text(encoding="utf-8")


def test_smoke_run_is_complete_and_verified(smoke_run):
    manifest = smoke_run.manifest
    for key in ("schema_version", "run_id", "status", "created_at_utc", "code_commit", "working_tree_dirty",
                "source_bundle_sha256", "config_sha256", "data_sha256", "split_sha256", "environment_sha256",
                "seed", "device", "stages", "artifacts", "verification"):
        assert key in manifest
    assert manifest["status"] == "succeeded"
    assert all(stage["status"] == "succeeded" for stage in manifest["stages"].values())
    assert verify_run(smoke_run)["status"] == "passed"


def test_predictions_carry_temporal_provenance(smoke_run):
    predictions = read_table(run_path(smoke_run.run_dir, "predictions"))
    for column in ("issued_at", "intervention_date", "target_start", "target_end", "label_cutoff", "model_version"):
        assert predictions[column].ne("").all()
    assert (predictions["target_start"] > predictions["intervention_date"]).all()
    assert (predictions["target_end"] <= "2026-09-08").all()


def test_two_identical_runs_produce_identical_results(tmp_path, smoke_run):
    ctx, code = run_smoke(tmp_path)
    assert code == 0
    for name in COMPARED:
        pd.testing.assert_frame_equal(_table(ctx, name), _table(smoke_run, name))


def test_interruption_then_resume_matches_uninterrupted_run(tmp_path, smoke_run, monkeypatch):
    monkeypatch.setenv("RESEARCH_INTERRUPT_STAGE", "evaluate")
    ctx, code = run_smoke(tmp_path)
    assert code == 130
    manifest = load_manifest(ctx.run_dir)
    assert manifest["status"] == "interrupted"
    assert manifest["stages"]["evaluate"]["status"] == "interrupted"
    assert manifest["stages"]["predict"]["status"] == "succeeded"
    assert verify_run(ctx)["status"] == "failed"

    monkeypatch.delenv("RESEARCH_INTERRUPT_STAGE")
    resumed = open_run(ROOT, ctx.run_id, tmp_path / "runs", tmp_path / "processed", quiet=True)
    refresh_facts(resumed)
    assert execute(resumed) == 0
    stages = resumed.manifest["stages"]
    assert stages["predict"]["attempt"] == 1 and stages["evaluate"]["attempt"] == 2
    assert verify_run(resumed)["status"] == "passed"
    for name in COMPARED:
        pd.testing.assert_frame_equal(_table(resumed, name), _table(smoke_run, name))


def test_injected_failure_gives_nonzero_exit_and_blocks_release(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_ROOT", str(ROOT))
    monkeypatch.setenv("RESEARCH_FAIL_STAGE", "diagnostics")
    code = cli.main(["--runs-dir", str(tmp_path / "runs"), "--processed-dir", str(tmp_path / "processed"),
                     "--quiet", "run", "--config", str(SMOKE_CONFIG), "--set", "inference.bootstrap_reps=300"])
    assert code == 1
    ctx = open_run(ROOT, "latest", tmp_path / "runs", tmp_path / "processed", quiet=True)
    assert ctx.manifest["status"] == "failed"
    assert ctx.manifest["stages"]["diagnostics"]["status"] == "failed"
    assert ctx.manifest["stages"].get("report", {}).get("status") != "succeeded"
    junit = tmp_path / "junit.xml"
    junit.write_text(CLEAN_JUNIT, encoding="utf-8")
    code, out, problems = release_run(ctx, junit, tmp_path / "releases")
    assert code == 1 and out is None
    assert any("verification failed" in problem for problem in problems)


def test_same_size_data_change_invalidates_processed_cache(tmp_path):
    snapshot = _snapshot_copy(tmp_path)
    overrides = {"data": {"snapshot": str(snapshot)}}
    first, code = run_smoke(tmp_path, overrides, only=UP_TO_TRANSFORM)
    assert code == 2 and first.manifest["status"] == "incomplete"

    path = snapshot / "gsc_daily.csv"
    original = path.read_bytes()
    lines = original.split(b"\n")
    for number, line in enumerate(lines[1:], start=1):
        fields = line.split(b",")
        if len(fields) == 6 and fields[5] and int(fields[4]) >= 10 and int(fields[4]) % 10 != 9:
            fields[4] = str(int(fields[4]) + 1).encode()
            lines[number] = b",".join(fields)
            break
    changed = b"\n".join(lines)
    assert len(changed) == len(original) and changed != original
    path.write_bytes(changed)
    _reseal(snapshot)

    second, code = run_smoke(tmp_path, overrides, only=UP_TO_TRANSFORM)
    assert code == 2
    assert second.manifest["data_sha256"] != first.manifest["data_sha256"]
    assert second.processed_dir != first.processed_dir
    assert "reused" not in _log(second)
    assert sha256_file(second.processed_dir / "panel_page_day.csv") != \
        sha256_file(first.processed_dir / "panel_page_day.csv")


def test_damaged_processed_file_is_rebuilt_not_trusted(tmp_path):
    first, _ = run_smoke(tmp_path, only=UP_TO_TRANSFORM)
    panel = first.processed_dir / "panel_page_day.csv"
    original = sha256_file(panel)
    panel.write_bytes(panel.read_bytes().replace(b"P01", b"P02", 1))
    second, _ = run_smoke(tmp_path, only=UP_TO_TRANSFORM)
    assert second.processed_dir == first.processed_dir
    assert "stale or damaged" in _log(second)
    assert sha256_file(panel) == original


def test_unsealed_data_change_stops_the_run(tmp_path):
    snapshot = _snapshot_copy(tmp_path)
    path = snapshot / "authority.csv"
    path.write_bytes(path.read_bytes().replace(b",17\n", b",18\n"))
    ctx, code = run_smoke(tmp_path, {"data": {"snapshot": str(snapshot)}})
    assert code == 1
    assert ctx.manifest["stages"]["ingest"]["status"] == "failed"


def test_verify_recomputes_metrics_even_when_hashes_are_updated(tmp_path):
    ctx, code = run_smoke(tmp_path)
    assert code == 0
    path = run_path(ctx.run_dir, "metrics")
    frame = read_table(path)
    frame.loc[frame["hypothesis_id"] == "H1", "estimate"] += 0.01
    write_csv(path, frame)
    rel, sha = ctx.rel(path), sha256_file(path)
    ctx.manifest["stages"]["evaluate"]["outputs"][rel] = sha
    for artifact in ctx.manifest["artifacts"]:
        if artifact["path"] == rel:
            artifact["sha256"] = sha
    failed = {c["name"] for c in verify_run(ctx)["checks"] if not c["ok"]}
    assert "artifact_hashes" not in failed
    assert "metrics_recomputed_from_predictions" in failed


def test_resume_rebuilds_a_deleted_artifact(tmp_path):
    ctx, code = run_smoke(tmp_path)
    assert code == 0
    run_path(ctx.run_dir, "placebo").unlink()
    assert verify_run(ctx)["status"] == "failed"
    resumed = open_run(ROOT, ctx.run_id, tmp_path / "runs", tmp_path / "processed", quiet=True)
    refresh_facts(resumed)
    assert execute(resumed) == 0
    assert resumed.manifest["stages"]["diagnostics"]["attempt"] == 2
    assert resumed.manifest["stages"]["evaluate"]["attempt"] == 1
    assert verify_run(resumed)["status"] == "passed"
