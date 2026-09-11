"""Command line interface: ``python -m research <command>``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .config import ConfigError


def _overrides(pairs: list[str]) -> dict:
    result: dict = {}
    for pair in pairs or []:
        key, _, raw = pair.partition("=")
        target = result
        parts = key.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = yaml.safe_load(raw)
    return result


def _dirs(args, root: Path) -> tuple[Path, Path]:
    return (Path(args.runs_dir) if args.runs_dir else root / "runs",
            Path(args.processed_dir) if args.processed_dir else root / "data" / "processed")


def _print_verification(result: dict) -> None:
    for check in result["checks"]:
        mark = "OK  " if check["ok"] else "FAIL"
        print(f"  {mark} {check['name']}" + (f" - {check['detail']}" if check["detail"] else ""))
    print(f"verification: {result['status']}")


def main(argv: list[str] | None = None) -> int:
    from .pipeline import create_run, execute, open_run, project_root, refresh_facts

    parser = argparse.ArgumentParser(prog="python -m research", description=__doc__)
    parser.add_argument("--runs-dir", help=argparse.SUPPRESS)
    parser.add_argument("--processed-dir", help=argparse.SUPPRESS)
    parser.add_argument("--quiet", action="store_true", help="do not echo the run log")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="check runtime, dependencies, configs, data and paths")
    doctor.add_argument("--config", action="append", default=[])
    smoke = sub.add_parser("smoke", help="small offline end-to-end run on the synthetic snapshot")
    smoke.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    run = sub.add_parser("run", help="run every stage for a configuration")
    run.add_argument("--config", required=True)
    run.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    for name, text in (("resume", "re-check finished stages and continue"),
                       ("verify", "check completeness, hashes, provenance and metrics"),
                       ("status", "print stage statuses")):
        command = sub.add_parser(name, help=text)
        command.add_argument("--run-id", required=True, help="run id or 'latest'")
    report = sub.add_parser("report", help="rebuild tables, figures and exports of a run")
    report.add_argument("--run-id", required=True)
    report.add_argument("--force", action="store_true")
    release = sub.add_parser("release", help="publish a verified run with its test report")
    release.add_argument("--run-id", required=True)
    release.add_argument("--junit", required=True)
    release.add_argument("--site-dir")
    fixtures = sub.add_parser("fixtures", help="generate the synthetic smoke snapshot")
    fixtures.add_argument("--out", required=True)
    crawl = sub.add_parser("crawl", help="crawl a site into a raw snapshot folder (network)")
    crawl.add_argument("--url", required=True)
    crawl.add_argument("--out", required=True, help="e.g. data/raw/site_2026-09/crawl/before")
    crawl.add_argument("--max-pages", type=int, default=200)
    crawl.add_argument("--delay", type=float, default=1.0)
    crawl.add_argument("--from-dir", help="serve pages from a local folder instead of the network")
    checksums = sub.add_parser("checksums", help="write SHA256SUMS for a new raw snapshot")
    checksums.add_argument("--snapshot", required=True)

    args = parser.parse_args(argv)
    root = project_root()
    runs_dir, processed_dir = _dirs(args, root)

    try:
        if args.command == "doctor":
            from .doctor import run_doctor

            configs = [Path(c) for c in args.config] or sorted((root / "configs").glob("*.yaml"))
            ok, checks = run_doctor(root, configs)
            for check in checks:
                print(f"  {check['status'].upper():5} {check['name']}" + (f" - {check['detail']}" if check["detail"] else ""))
            print("doctor: " + ("ok" if ok else "problems found"))
            return 0 if ok else 1

        if args.command in {"smoke", "run"}:
            config = root / "configs" / "smoke.yaml" if args.command == "smoke" else Path(args.config)
            ctx = create_run(root, config, _overrides(args.set), runs_dir, processed_dir, args.quiet)
            print(f"run_id={ctx.run_id}")
            code = execute(ctx)
            print(f"status={ctx.manifest['status']}")
            if args.command == "smoke" and code == 0:
                from .verify import verify_run

                result = verify_run(ctx)
                _print_verification(result)
                return 0 if result["status"] == "passed" else 1
            return code

        if args.command == "fixtures":
            from .synthetic import generate_snapshot

            print(f"data_sha256={generate_snapshot(Path(args.out))}")
            return 0

        if args.command == "crawl":
            from .crawl import DirectoryFetcher, HttpFetcher, crawl as crawl_site, write_crawl

            fetcher = DirectoryFetcher(args.from_dir, args.url) if args.from_dir else HttpFetcher(args.delay)
            records = crawl_site(args.url, fetcher, args.max_pages)
            write_crawl(records, Path(args.out))
            print(f"crawled {len(records)} urls into {args.out}")
            return 0

        if args.command == "checksums":
            from .io_utils import atomic_write_text, format_sha256sums, read_sha256sums, tree_sha256

            snapshot = Path(args.snapshot)
            tree, files = tree_sha256(snapshot)
            sums = snapshot / "SHA256SUMS"
            if sums.exists():
                if read_sha256sums(sums) == files:
                    print(f"SHA256SUMS already matches; data_sha256={tree}")
                    return 0
                print("SHA256SUMS exists and differs: raw snapshots are immutable, create a new snapshot folder",
                      file=sys.stderr)
                return 1
            atomic_write_text(sums, format_sha256sums(files))
            print(f"wrote {sums}; data_sha256={tree}")
            return 0

        ctx = open_run(root, args.run_id, runs_dir, processed_dir, args.quiet)
        if args.command == "status":
            print(f"run_id={ctx.run_id} status={ctx.manifest['status']} "
                  f"verification={ctx.manifest.get('verification', {}).get('status', '-')}")
            for name, record in ctx.manifest["stages"].items():
                print(f"  {name:12} {record['status']:12} attempt={record.get('attempt', 0)}"
                      + (f" error={record['error']}" if record.get("error") else ""))
            return 0
        if args.command == "resume":
            changes = refresh_facts(ctx)
            for key, change in changes.items():
                print(f"changed since last attempt: {key}")
            code = execute(ctx)
            print(f"status={ctx.manifest['status']}")
            return code
        if args.command == "verify":
            from .verify import verify_run

            result = verify_run(ctx)
            _print_verification(result)
            return 0 if result["status"] == "passed" else 1
        if args.command == "report":
            changes = refresh_facts(ctx)
            if changes:
                print(f"code, data, config or environment changed ({sorted(changes)}); run resume instead",
                      file=sys.stderr)
                return 1
            return execute(ctx, only=["report"], force=args.force)
        if args.command == "release":
            from .release import release_run

            code, out, problems = release_run(ctx, args.junit, root / "releases",
                                              Path(args.site_dir) if args.site_dir else None)
            for problem in problems:
                print(f"release refused: {problem}", file=sys.stderr)
            if out:
                print(f"released {ctx.run_id} into {out}")
            return code
    except (ConfigError, FileNotFoundError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1
