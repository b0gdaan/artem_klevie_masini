"""Environment and project health checks."""
from __future__ import annotations

import shutil
import sys
import tempfile
from importlib import metadata
from pathlib import Path

import research

from .config import ConfigError, load_config
from .data import validate_snapshot


def _lock(root: Path) -> dict[str, str]:
    path = root / "requirements.lock"
    pins = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if "==" in line:
                name, version = line.split("==", 1)
                pins[name.strip()] = version.strip()
    return pins


def run_doctor(root: Path, configs: list[Path]) -> tuple[bool, list[dict]]:
    checks = []

    def add(name, status, detail=""):
        checks.append({"name": name, "status": status, "detail": detail})

    version = sys.version_info
    add("python", "ok" if version[:2] == (3, 11) else "warn" if version >= (3, 11) else "error",
        f"{sys.version.split()[0]} (lock was produced with 3.11)")

    pins = _lock(root)
    if not pins:
        add("requirements.lock", "error", "missing or empty")
    mismatched = []
    for name, pinned in sorted(pins.items()):
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            installed = None
        if installed != pinned:
            mismatched.append(f"{name} {installed} != {pinned}")
    if pins:
        add("locked_packages", "ok" if not mismatched else "error",
            f"{len(pins)} pinned" if not mismatched else "; ".join(mismatched[:6]))

    package_dir = Path(research.__file__).resolve().parent
    expected = (root / "src" / "research").resolve()
    add("package_location", "ok" if package_dir == expected else "error",
        f"{package_dir}" + ("" if package_dir == expected else f" (expected {expected}; reinstall with pip install -e .)"))

    for config_path in configs:
        try:
            cfg = load_config(config_path)
        except (ConfigError, OSError) as exc:
            add(f"config:{config_path.name}", "error", str(exc))
            continue
        add(f"config:{config_path.name}", "ok", f"mode={cfg['mode']}, {len(cfg['hypotheses'])} hypotheses")
        snapshot = Path(cfg["data"]["snapshot"])
        snapshot = snapshot if snapshot.is_absolute() else root / snapshot
        if not snapshot.is_dir():
            add(f"data:{config_path.name}", "warn", f"snapshot {snapshot} not present (see docs/DATA.md)")
            continue
        errors = [i for i in validate_snapshot(snapshot, cfg) if i["severity"] == "error"]
        add(f"data:{config_path.name}", "ok" if not errors else "error",
            "schema and SHA256SUMS valid" if not errors else f"{len(errors)} errors, first: {errors[0]}")

    for folder in (root / "runs", root / "data" / "processed", root / "releases"):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=folder):
                pass
            add(f"writable:{folder.relative_to(root).as_posix()}", "ok")
        except OSError as exc:
            add(f"writable:{folder.name}", "error", str(exc))
    free_mb = shutil.disk_usage(root).free // (1 << 20)
    add("disk_space", "ok" if free_mb > 500 else "warn", f"{free_mb} MB free")
    add("git", "ok" if shutil.which("git") else "warn", "needed for code_commit in manifests")
    return not any(c["status"] == "error" for c in checks), checks
