"""Locations and typed loaders of run artefacts."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RUN_PATHS = {
    "design": "split/design.csv",
    "placebo_design": "split/placebo_design.csv",
    "curve": "models/ctr_curve.json",
    "page_windows": "predictions/page_windows.csv",
    "predictions": "predictions/predictions.csv",
    "placebo_page_windows": "predictions/placebo_page_windows.csv",
    "placebo_predictions": "predictions/placebo_predictions.csv",
    "metrics": "metrics/metrics.csv",
    "ablation": "metrics/ablation.csv",
    "placebo": "metrics/placebo.csv",
    "report": "report",
}
PROCESSED_FILES = ("panel_segment_day.csv", "panel_page_day.csv", "audit_pages_before.csv",
                   "audit_issues_before.csv", "audit_pages_after.csv", "audit_issues_after.csv")
_TEXT = ["hypothesis_id", "arm", "window_key", "page", "role", "period", "start", "end", "intervention_date",
         "label_cutoff", "metric", "run_id", "model", "model_version", "split", "target_name", "issued_at",
         "target_start", "target_end", "date", "segment", "kind", "intervention", "compare_to", "decision",
         "decision_unadjusted", "status", "note", "url", "issue", "category", "detail"]


def run_path(run_dir: Path, name: str) -> Path:
    return Path(run_dir) / RUN_PATHS[name]


def read_table(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={c: str for c in _TEXT}, keep_default_na=False, na_values=[""])
    for column in frame.columns:
        if column in _TEXT:
            frame[column] = frame[column].fillna("")
    for column in ("eligible", "window_eligible"):
        if column in frame.columns:
            frame[column] = frame[column].astype(str).str.lower().eq("true")
    return frame
