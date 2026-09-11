"""Run manifest: the single record of what a run used, did and produced."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from .io_utils import atomic_write_text

STAGE_STATUSES = ("pending", "running", "succeeded", "failed", "interrupted")
RUN_STATUSES = ("pending", "running", "succeeded", "failed", "interrupted", "incomplete")
TRACKED_FACTS = ("code_commit", "working_tree_dirty", "source_bundle_sha256", "config_sha256",
                 "data_sha256", "environment_sha256")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_manifest(run_id: str, facts: dict) -> dict:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "status": "pending",
        "created_at_utc": utc_now(),
        "code_commit": facts["code_commit"],
        "working_tree_dirty": facts["working_tree_dirty"],
        "source_bundle_sha256": facts["source_bundle_sha256"],
        "config_sha256": facts["config_sha256"],
        "data_sha256": facts["data_sha256"],
        "split_sha256": None,
        "environment_sha256": facts["environment_sha256"],
        "seed": facts["seed"],
        "device": facts["device"],
        "config_name": facts["config_name"],
        "mode": facts["mode"],
        "package_version": facts["package_version"],
        "environment": facts["environment"],
        "stages": {},
        "artifacts": [],
        "verification": {},
    }


def manifest_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / "manifest.yaml"


def load_manifest(run_dir: str | Path) -> dict:
    path = manifest_path(run_dir)
    if not path.is_file():
        raise FileNotFoundError(f"no manifest at {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def save_manifest(run_dir: str | Path, manifest: dict) -> Path:
    text = yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120)
    return atomic_write_text(manifest_path(run_dir), text)
