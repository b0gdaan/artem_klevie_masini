"""Release a verified run together with its test report and checksums."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .artifacts import run_path
from .io_utils import atomic_write_bytes, format_sha256sums, sha256_file, tree_sha256, write_json
from .manifest import utc_now
from .report import PRINT_NAME, PUBLIC_NAME
from .verify import verify_run


def parse_junit(path: str | Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    cases = list(root.iter("testcase"))
    counted = {
        "tests": len(cases),
        "failures": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
        "skipped": sum(case.find("skipped") is not None for case in cases),
    }
    declared = {key: sum(int(suite.get(key, 0)) for suite in suites) for key in counted}
    return {**counted,
            "passed": counted["tests"] - counted["failures"] - counted["errors"] - counted["skipped"],
            "declared": declared, "attributes_consistent": declared == counted,
            "sha256": sha256_file(path)}


def release_run(ctx, junit: str | Path, releases_dir: Path, site_dir: Path | None = None) -> tuple[int, Path | None, list[str]]:
    problems = []
    verification = verify_run(ctx)
    if verification["status"] != "passed":
        failed = [c["name"] for c in verification["checks"] if not c["ok"]]
        problems.append(f"verification failed: {failed}")
    junit = Path(junit)
    summary = None
    if not junit.is_file():
        problems.append(f"JUnit report not found: {junit}")
    else:
        summary = parse_junit(junit)
        if summary["tests"] == 0:
            problems.append("JUnit report contains no tests")
        if summary["failures"] or summary["errors"]:
            problems.append(f"tests not clean: {summary['failures']} failed, {summary['errors']} errors")
        if not summary["attributes_consistent"]:
            problems.append("JUnit suite attributes disagree with test cases")
    out = releases_dir / ctx.run_id
    if out.exists():
        problems.append(f"{out} already exists; releases are immutable")
    if problems:
        return 1, None, problems

    run_dir = ctx.run_dir
    files = ["manifest.yaml", "config.effective.yaml", "metrics/metrics.csv", "metrics/ablation.csv",
             "metrics/placebo.csv", "predictions/predictions.csv"]
    files += [p.relative_to(run_dir).as_posix() for p in sorted(run_path(run_dir, "report").rglob("*")) if p.is_file()]
    for rel in files:
        atomic_write_bytes(out / rel, (run_dir / rel).read_bytes())
    atomic_write_bytes(out / "tests" / "junit.xml", junit.read_bytes())
    write_json(out / "RELEASE.json", {
        "run_id": ctx.run_id, "released_at_utc": utc_now(), "mode": ctx.config["mode"],
        "code_commit": ctx.manifest["code_commit"], "working_tree_dirty": ctx.manifest["working_tree_dirty"],
        "data_sha256": ctx.manifest["data_sha256"], "config_sha256": ctx.manifest["config_sha256"],
        "environment": ctx.manifest["environment"], "public_name": PUBLIC_NAME, "print_name": PRINT_NAME,
        "tests": summary, "verification_status": verification["status"],
    })
    _, sums = tree_sha256(out)
    atomic_write_bytes(out / "SHA256SUMS", format_sha256sums(sums).encode("utf-8"))

    if site_dir is not None:
        data_dir = Path(site_dir) / "data"
        atomic_write_bytes(data_dir / f"{PUBLIC_NAME}.json", (run_path(run_dir, "report") / "site_data.json").read_bytes())
        for figure in sorted((run_path(run_dir, "report") / "figures").glob("*.png")):
            atomic_write_bytes(data_dir / "figures" / figure.name, figure.read_bytes())
        write_json(data_dir / "release.json", {"run_id": ctx.run_id, "tests": summary,
                                               "release_sha256sums": sha256_file(out / "SHA256SUMS")})
    return 0, out, []
