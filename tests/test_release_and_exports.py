import math

import pytest

from conftest import ROOT, SMOKE_CONFIG, SMOKE_SNAPSHOT
from research.artifacts import read_table, run_path
from research.doctor import run_doctor
from research.io_utils import read_json, read_sha256sums, tree_sha256
from research.release import parse_junit, release_run
from research.synthetic import generate_snapshot

CLEAN = ('<testsuites><testsuite name="s" tests="2" failures="0" errors="0" skipped="0">'
         '<testcase name="a"/><testcase name="b"/></testsuite></testsuites>')
MIXED = ('<testsuite name="s" tests="5" failures="1" errors="1" skipped="1"><testcase name="ok1"/>'
         '<testcase name="ok2"/><testcase name="f"><failure message="x"/></testcase>'
         '<testcase name="e"><error message="y"/></testcase><testcase name="s"><skipped/></testcase></testsuite>')
HIDING = ('<testsuite name="s" tests="3" failures="0" errors="0" skipped="0"><testcase name="ok"/>'
          '<testcase name="f"><failure/></testcase><testcase name="s"><skipped/></testcase></testsuite>')


def _junit(tmp_path, text, name="junit.xml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_junit_counts_failed_error_and_skipped(tmp_path):
    summary = parse_junit(_junit(tmp_path, MIXED))
    assert (summary["tests"], summary["failures"], summary["errors"], summary["skipped"], summary["passed"]) == \
        (5, 1, 1, 1, 2)
    assert summary["attributes_consistent"]


def test_parse_junit_detects_attributes_hiding_failures(tmp_path):
    summary = parse_junit(_junit(tmp_path, HIDING))
    assert summary["failures"] == 1 and summary["skipped"] == 1
    assert not summary["attributes_consistent"]


@pytest.mark.parametrize("text, message", [(MIXED, "tests not clean"), (HIDING, "disagree")])
def test_release_refuses_unclean_test_reports(tmp_path, smoke_run, text, message):
    code, out, problems = release_run(smoke_run, _junit(tmp_path, text), tmp_path / "releases")
    assert code == 1 and out is None
    assert any(message in problem for problem in problems)


def test_release_writes_checksummed_bundle_and_public_site_data(tmp_path, smoke_run):
    junit = _junit(tmp_path, CLEAN)
    code, out, problems = release_run(smoke_run, junit, tmp_path / "releases", tmp_path / "site")
    assert code == 0, problems
    assert read_sha256sums(out / "SHA256SUMS") == tree_sha256(out)[1]
    release = read_json(out / "RELEASE.json")
    assert release["tests"]["tests"] == 2 and release["tests"]["skipped"] == 0
    assert release["public_name"] != release["print_name"]
    report_data = read_json(run_path(smoke_run.run_dir, "report") / "site_data.json")
    assert read_json(tmp_path / "site" / "data" / "demo_public.json") == report_data
    code, _, problems = release_run(smoke_run, junit, tmp_path / "releases")
    assert code == 1 and any("immutable" in problem for problem in problems)


def test_site_export_matches_metrics_table(smoke_run):
    site = read_json(run_path(smoke_run.run_dir, "report") / "site_data.json")
    metrics = read_table(run_path(smoke_run.run_dir, "metrics")).set_index("hypothesis_id")
    assert site["run_id"] == smoke_run.run_id and site["mode"] == "synthetic"
    assert site["model_version"] == "did-v2"
    assert site["data_period"]["end"] <= site["available_until"]
    for item in site["hypotheses"]:
        row = metrics.loc[item["hypothesis_id"]]
        assert item["decision"] == row["decision"]
        for column in ("estimate", "ci_low_adj", "ci_high_adj"):
            if item[column] is None:
                assert math.isnan(row[column])
            else:
                assert item[column] == pytest.approx(row[column], abs=1e-12)


def test_claims_reference_files_of_the_same_run(smoke_run):
    claims = read_table(run_path(smoke_run.run_dir, "report") / "claims.csv")
    assert claims["run_id"].eq(smoke_run.run_id).all()
    assert all((smoke_run.run_dir / file).is_file() for file in claims["file"])


def test_generator_is_deterministic_and_matches_committed_snapshot(tmp_path):
    first = generate_snapshot(tmp_path / "a")
    second = generate_snapshot(tmp_path / "b")
    assert first == second == tree_sha256(SMOKE_SNAPSHOT)[0]


def test_generator_refuses_to_overwrite_a_snapshot(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "f.txt").write_text("1", encoding="utf-8")
    with pytest.raises(FileExistsError):
        generate_snapshot(tmp_path / "x")


def test_known_synthetic_effects_are_recovered(smoke_run):
    metrics = read_table(run_path(smoke_run.run_dir, "metrics")).set_index("hypothesis_id")
    truth = read_json(SMOKE_SNAPSHOT / "ground_truth.json")["expected_estimands"]
    assert metrics.loc["H1", "estimate"] == pytest.approx(truth["H1"], abs=0.03)
    assert abs(metrics.loc["H4", "estimate"] - truth["H4"]) < 0.03
    assert metrics.loc["H2", "ci_low_adj"] <= truth["H2"] <= metrics.loc["H2", "ci_high_adj"]
    assert metrics.loc["H3", "ci_low_adj"] <= truth["H3"] <= metrics.loc["H3", "ci_high_adj"]
    placebo = read_table(run_path(smoke_run.run_dir, "placebo")).set_index("hypothesis_id")
    assert placebo.loc[["H1", "H4"], "contains_zero"].all()


def test_doctor_accepts_the_repository_setup():
    ok, checks = run_doctor(ROOT, [SMOKE_CONFIG])
    assert ok, [c for c in checks if c["status"] == "error"]
