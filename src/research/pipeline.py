"""Stage runner with fingerprints, resume and fault injection.

A stage is skipped only when its previous record is ``succeeded``, its input
fingerprint (code bundle, effective config, data, environment and the output
hashes of its dependencies) is unchanged and every recorded output still has
the recorded hash. Starting a stage marks all its dependents ``pending``.
"""
from __future__ import annotations

import os
import platform
import secrets
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import yaml

from . import __version__
from .config import STAGE_NAMES, config_sha256, load_config
from .io_utils import atomic_write_text, sha256_file, sha256_json, tree_sha256
from .manifest import TRACKED_FACTS, load_manifest, new_manifest, save_manifest, utc_now

LOCK_PACKAGES = ("numpy", "pandas", "PyYAML", "beautifulsoup4", "matplotlib", "requests", "pytest")


class StageInterrupted(RuntimeError):
    pass


def project_root() -> Path:
    override = os.environ.get("RESEARCH_ROOT")
    if override:
        return Path(override).resolve()
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "configs").is_dir() and (candidate / "src" / "research").is_dir():
            return candidate
    return Path(__file__).resolve().parents[2]


def source_bundle_sha256() -> str:
    package = Path(__file__).resolve().parent
    return sha256_json({p.relative_to(package).as_posix(): sha256_file(p)
                        for p in sorted(package.rglob("*.py"))})


def git_facts(root: Path) -> tuple[str, bool]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True,
                                         stderr=subprocess.DEVNULL).strip()
        status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                         cwd=root, text=True, stderr=subprocess.DEVNULL)
        return commit, bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


def environment_facts() -> tuple[dict, str]:
    packages = {}
    for name in LOCK_PACKAGES:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    env = {"python": platform.python_version(), "implementation": platform.python_implementation(),
           "system": platform.system(), "machine": platform.machine(), "packages": packages}
    return env, sha256_json(env)


def collect_facts(root: Path, config: dict, snapshot: Path) -> dict:
    commit, dirty = git_facts(root)
    env, env_sha = environment_facts()
    return {
        "code_commit": commit, "working_tree_dirty": dirty,
        "source_bundle_sha256": source_bundle_sha256(), "config_sha256": config_sha256(config),
        "data_sha256": tree_sha256(snapshot)[0] if snapshot.is_dir() else None,
        "environment_sha256": env_sha, "environment": env, "seed": config["seed"],
        "device": f"cpu ({platform.machine()}, {os.cpu_count()} logical cores)",
        "config_name": config["name"], "mode": config["mode"], "package_version": __version__,
    }


@dataclass
class Context:
    root: Path
    config: dict
    run_id: str
    run_dir: Path
    processed_root: Path
    manifest: dict
    quiet: bool = False

    @property
    def snapshot_dir(self) -> Path:
        path = Path(self.config["data"]["snapshot"])
        return path if path.is_absolute() else self.root / path

    @property
    def processed_dir(self) -> Path:
        key = f"{self.manifest['data_sha256'][:16]}-{self.manifest['source_bundle_sha256'][:12]}"
        return self.processed_root / key

    def rel(self, path: str | Path) -> str:
        resolved = Path(path).resolve()
        try:
            return resolved.relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return resolved.as_posix()

    def resolve(self, rel: str) -> Path:
        path = Path(rel)
        return path if path.is_absolute() else self.root / path

    def save(self) -> None:
        save_manifest(self.run_dir, self.manifest)

    def log(self, message: str) -> None:
        line = f"{utc_now()} {message}"
        log_path = self.run_dir / "logs" / "run.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
        if not self.quiet:
            print(line, file=sys.stderr)


def create_run(root: Path, config_path: str | Path, overrides: dict | None = None,
               runs_dir: Path | None = None, processed_root: Path | None = None,
               quiet: bool = False) -> Context:
    config = load_config(config_path, overrides)
    runs_dir = Path(runs_dir or root / "runs")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{config['name']}-{stamp}-{secrets.token_hex(3)}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    atomic_write_text(run_dir / "config.effective.yaml",
                      yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    snapshot = Path(config["data"]["snapshot"])
    snapshot = snapshot if snapshot.is_absolute() else root / snapshot
    manifest = new_manifest(run_id, collect_facts(root, config, snapshot))
    ctx = Context(root, config, run_id, run_dir, Path(processed_root or root / "data" / "processed"),
                  manifest, quiet)
    manifest["config_source"] = ctx.rel(config_path)
    ctx.save()
    atomic_write_text(runs_dir / "LATEST", run_id + "\n")
    return ctx


def resolve_run_id(runs_dir: Path, run_id: str) -> str:
    if run_id == "latest":
        latest = runs_dir / "LATEST"
        if not latest.is_file():
            raise FileNotFoundError("no runs yet (runs/LATEST is missing)")
        return latest.read_text(encoding="utf-8").strip()
    return run_id


def open_run(root: Path, run_id: str, runs_dir: Path | None = None, processed_root: Path | None = None,
             quiet: bool = False) -> Context:
    runs_dir = Path(runs_dir or root / "runs")
    run_id = resolve_run_id(runs_dir, run_id)
    run_dir = runs_dir / run_id
    manifest = load_manifest(run_dir)
    config = load_config(run_dir / "config.effective.yaml")
    return Context(root, config, run_id, run_dir, Path(processed_root or root / "data" / "processed"),
                   manifest, quiet)


def refresh_facts(ctx: Context) -> dict:
    """Record changes of code, data, config or environment since the run was created."""
    current = collect_facts(ctx.root, ctx.config, ctx.snapshot_dir)
    changes = {key: {"old": ctx.manifest.get(key), "new": current[key]}
               for key in TRACKED_FACTS if ctx.manifest.get(key) != current[key]}
    if changes:
        ctx.manifest.setdefault("resume_history", []).append({"at_utc": utc_now(), "changes": changes})
        for key in TRACKED_FACTS:
            ctx.manifest[key] = current[key]
        ctx.manifest["environment"] = current["environment"]
        ctx.save()
    return changes


def stage_fingerprint(ctx: Context, name: str, deps: list[str]) -> str:
    manifest = ctx.manifest
    return sha256_json({
        "stage": name,
        **{key: manifest.get(key) for key in ("source_bundle_sha256", "config_sha256", "data_sha256",
                                              "environment_sha256")},
        "dependencies": {dep: manifest["stages"][dep].get("outputs", {}) for dep in deps},
    })


def outputs_intact(ctx: Context, record: dict) -> bool:
    outputs = record.get("outputs") or {}
    return bool(outputs) and all(ctx.resolve(p).is_file() and sha256_file(ctx.resolve(p)) == sha
                                 for p, sha in outputs.items())


def dependents(stages, name: str) -> list[str]:
    found, frontier = [], {name}
    for stage_name, deps, _ in stages:
        if frontier & set(deps):
            found.append(stage_name)
            frontier.add(stage_name)
    return found


def _inject_faults(name: str) -> None:
    if os.environ.get("RESEARCH_FAIL_STAGE") == name:
        raise RuntimeError(f"injected failure in stage {name}")
    if os.environ.get("RESEARCH_INTERRUPT_STAGE") == name:
        raise StageInterrupted(f"injected interruption in stage {name}")


def _refresh_artifacts(ctx: Context, stages) -> None:
    ctx.manifest["artifacts"] = [
        {"stage": name, "path": path, "sha256": sha}
        for name, _, _ in stages
        if ctx.manifest["stages"].get(name, {}).get("status") == "succeeded"
        for path, sha in sorted(ctx.manifest["stages"][name].get("outputs", {}).items())
    ]


def execute(ctx: Context, only: list[str] | None = None, force: bool = False) -> int:
    from .stages import STAGES

    manifest = ctx.manifest
    required = ctx.config.get("required_stages", list(STAGE_NAMES))
    manifest["status"] = "running"
    ctx.save()
    for name, deps, function in STAGES:
        if only is not None and name not in only:
            continue
        record = manifest["stages"].setdefault(name, {"status": "pending", "attempt": 0})
        blocked = [dep for dep in deps if manifest["stages"].get(dep, {}).get("status") != "succeeded"]
        if blocked:
            record.update(status="pending", error=f"blocked by unfinished stages {blocked}")
            continue
        fingerprint = stage_fingerprint(ctx, name, deps)
        if (not force and record.get("status") == "succeeded"
                and record.get("input_sha256") == fingerprint and outputs_intact(ctx, record)):
            ctx.log(f"[{name}] reused verified outputs")
            continue
        for dependent in dependents(STAGES, name):
            if dependent in manifest["stages"] and manifest["stages"][dependent]["status"] == "succeeded":
                manifest["stages"][dependent].update(status="pending", error=f"invalidated by rerun of {name}")
        manifest["verification"] = {"status": "stale"} if manifest.get("verification") else {}
        record.update(status="running", attempt=int(record.get("attempt", 0)) + 1, started_at_utc=utc_now(),
                      finished_at_utc=None, input_sha256=fingerprint,
                      inputs={dep: sha256_json(manifest["stages"][dep]["outputs"]) for dep in deps},
                      outputs={}, error=None)
        ctx.save()
        ctx.log(f"[{name}] started (attempt {record['attempt']})")
        try:
            _inject_faults(name)
            outputs = {}
            for path in sorted({Path(p) for p in function(ctx)}, key=lambda p: p.as_posix()):
                if not path.is_file():
                    raise RuntimeError(f"stage {name} did not produce {path}")
                outputs[ctx.rel(path)] = sha256_file(path)
            record.update(status="succeeded", finished_at_utc=utc_now(), outputs=outputs)
            ctx.save()
            ctx.log(f"[{name}] succeeded, {len(outputs)} outputs")
        except (KeyboardInterrupt, StageInterrupted) as exc:
            record.update(status="interrupted", finished_at_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
            manifest["status"] = "interrupted"
            _refresh_artifacts(ctx, STAGES)
            ctx.save()
            ctx.log(f"[{name}] interrupted: {exc}")
            return 130
        except Exception as exc:  # noqa: BLE001 - every failure is recorded in the manifest
            record.update(status="failed", finished_at_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
            manifest["status"] = "failed"
            _refresh_artifacts(ctx, STAGES)
            ctx.save()
            ctx.log(f"[{name}] FAILED: {type(exc).__name__}: {exc}")
            return 1
    _refresh_artifacts(ctx, STAGES)
    complete = all(manifest["stages"].get(stage, {}).get("status") == "succeeded" for stage in required)
    manifest["status"] = "succeeded" if complete else "incomplete"
    ctx.save()
    return 0 if complete else 2
