"""Experiment configuration: loading, overrides and validation."""
from __future__ import annotations

import copy
from datetime import date, datetime
from pathlib import Path

import yaml

from .io_utils import sha256_json

KINDS = {"did", "did_difference", "descriptive"}
METRICS = {"position", "ctr_adjusted", "clicks", "domain_authority"}
INTERVENTIONS = {"technical", "content", "local", "accessibility", "links"}
SEGMENTS = {"all", "local", "general"}
MODES = {"synthetic", "snapshot"}
STAGE_NAMES = ("ingest", "validate", "transform", "split", "fit",
               "predict", "evaluate", "diagnostics", "report")


class ConfigError(ValueError):
    pass


def _normalize(value):
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def deep_merge(base: dict, extra: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: str | Path, overrides: dict | None = None) -> dict:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    config = _normalize(deep_merge(raw or {}, overrides or {}))
    errors = validate_config(config)
    if errors:
        raise ConfigError("; ".join(errors))
    return config


def config_sha256(config: dict) -> str:
    """Hash of the effective configuration (after overrides), independent of YAML formatting."""
    return sha256_json(config)


def _is_date(text) -> bool:
    try:
        date.fromisoformat(str(text))
        return True
    except ValueError:
        return False


def validate_config(cfg: dict) -> list[str]:
    errors = []
    if cfg.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for key in ("name", "seed", "mode", "data", "design", "inference", "hypotheses"):
        if key not in cfg:
            errors.append(f"missing key: {key}")
    if errors:
        return errors
    if cfg["mode"] not in MODES:
        errors.append(f"mode must be one of {sorted(MODES)}")
    if not isinstance(cfg["seed"], int):
        errors.append("seed must be an integer")

    data = cfg["data"]
    for key in ("snapshot", "gsc_lag_days", "analysis_cutoff"):
        if key not in data:
            errors.append(f"missing key: data.{key}")
    if "analysis_cutoff" in data and not _is_date(data["analysis_cutoff"]):
        errors.append("data.analysis_cutoff must be an ISO date")

    design = cfg["design"]
    for key in ("pre_days", "buffer_days", "ramp_days", "post_days", "min_post_days",
                "min_days_per_window", "placebo_shift_days"):
        if not isinstance(design.get(key), int) or design.get(key) < 0:
            errors.append(f"design.{key} must be a non-negative integer")
    if "control_group" not in design:
        errors.append("missing key: design.control_group")
    if not errors and design["min_post_days"] > design["post_days"]:
        errors.append("design.min_post_days cannot exceed design.post_days")

    inference = cfg["inference"]
    if not isinstance(inference.get("bootstrap_reps"), int) or inference.get("bootstrap_reps", 0) < 100:
        errors.append("inference.bootstrap_reps must be an integer >= 100")
    if not 0.5 < float(inference.get("ci_level", 0)) < 1:
        errors.append("inference.ci_level must be in (0.5, 1)")
    if inference.get("multiplicity") not in {"bonferroni", "none"}:
        errors.append("inference.multiplicity must be 'bonferroni' or 'none'")

    seen = set()
    for index, hyp in enumerate(cfg["hypotheses"]):
        where = f"hypotheses[{index}]"
        hid = hyp.get("id")
        if not hid or hid in seen:
            errors.append(f"{where}: id missing or duplicated")
        seen.add(hid)
        if hyp.get("kind") not in KINDS:
            errors.append(f"{where}: kind must be one of {sorted(KINDS)}")
        if hyp.get("metric") not in METRICS:
            errors.append(f"{where}: metric must be one of {sorted(METRICS)}")
        if hyp.get("intervention") not in INTERVENTIONS:
            errors.append(f"{where}: intervention must be one of {sorted(INTERVENTIONS)}")
        if hyp.get("segment", "all") not in SEGMENTS:
            errors.append(f"{where}: segment must be one of {sorted(SEGMENTS)}")
        if not isinstance(hyp.get("threshold"), (int, float)):
            errors.append(f"{where}: threshold must be a number")
        if hyp.get("kind") == "did_difference" and hyp.get("compare_to") not in INTERVENTIONS:
            errors.append(f"{where}: did_difference needs compare_to")
        if hyp.get("kind") == "descriptive" and not isinstance(hyp.get("horizon_days"), int):
            errors.append(f"{where}: descriptive needs integer horizon_days")
        if hyp.get("kind") in {"did", "did_difference"} and hyp.get("metric") == "domain_authority":
            errors.append(f"{where}: domain_authority is site-level and only allowed for descriptive")
    required = cfg.get("required_stages", list(STAGE_NAMES))
    unknown = set(required) - set(STAGE_NAMES)
    if unknown:
        errors.append(f"required_stages has unknown stages: {sorted(unknown)}")
    return errors


def inferential(cfg: dict) -> list[dict]:
    return [h for h in cfg["hypotheses"] if h["kind"] in {"did", "did_difference"}]


def arms(hyp: dict) -> dict[str, str]:
    """Map arm name to intervention type; a difference hypothesis has two treated arms."""
    if hyp["kind"] == "did_difference":
        return {"a": hyp["intervention"], "b": hyp["compare_to"]}
    return {"a": hyp["intervention"]}
