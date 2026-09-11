"""Raw snapshot layout, loading and schema validation.

A snapshot directory is immutable once written. Its ``SHA256SUMS`` lists every
file; the pipeline refuses to run when the listing and the files disagree.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .io_utils import read_sha256sums, tree_sha256

SCHEMAS = {
    "pages.csv": ["page", "url", "design_group"],
    "gsc_daily.csv": ["date", "page", "segment", "clicks", "impressions", "position"],
    "interventions.csv": ["intervention_id", "page", "type", "date", "description"],
    "lighthouse.csv": ["page", "snapshot", "date", "performance", "accessibility", "seo",
                       "lcp_ms", "cls", "inp_ms"],
    "authority.csv": ["date", "metric", "source", "value"],
    "crawl/before/index.csv": ["url", "file", "status", "content_type"],
    "crawl/after/index.csv": ["url", "file", "status", "content_type"],
}
REQUIRED_FILES = ["SNAPSHOT.yaml", "SHA256SUMS", *SCHEMAS]
SITE_WIDE_TYPES = {"links"}


class DataError(RuntimeError):
    pass


def available_until(cfg: dict) -> str:
    """Last date whose Search Console values are final at the analysis cutoff."""
    cutoff = date.fromisoformat(cfg["data"]["analysis_cutoff"])
    return (cutoff - timedelta(days=int(cfg["data"]["gsc_lag_days"]))).isoformat()


def load_tables(snapshot: str | Path) -> dict[str, pd.DataFrame]:
    snapshot = Path(snapshot)
    text_columns = {"page": str, "url": str, "design_group": str, "segment": str, "date": str,
                    "intervention_id": str, "type": str, "description": str, "snapshot": str,
                    "metric": str, "source": str, "file": str, "content_type": str}
    tables = {}
    for name, columns in SCHEMAS.items():
        path = snapshot / name
        if path.is_file():
            frame = pd.read_csv(path, dtype=text_columns, keep_default_na=False, na_values=[""])
            for column in frame.columns:
                if column in text_columns and frame[column].dtype == object:
                    frame[column] = frame[column].fillna("")
            tables[name] = frame
    return tables


def _issue(code: str, file: str, detail: str, severity: str = "error") -> dict:
    return {"severity": severity, "code": code, "file": file, "detail": detail}


def _bad_dates(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    return parsed.isna()


def validate_snapshot(snapshot: str | Path, cfg: dict) -> list[dict]:
    snapshot = Path(snapshot)
    issues: list[dict] = []
    for name in REQUIRED_FILES:
        if not (snapshot / name).is_file():
            issues.append(_issue("missing_file", name, "required file is absent"))
    if issues:
        return issues

    _, actual = tree_sha256(snapshot)
    declared = read_sha256sums(snapshot / "SHA256SUMS")
    for rel in sorted(set(actual) | set(declared)):
        if rel not in declared:
            issues.append(_issue("checksum_missing", rel, "file not listed in SHA256SUMS"))
        elif rel not in actual:
            issues.append(_issue("checksum_extra", rel, "listed file does not exist"))
        elif actual[rel] != declared[rel]:
            issues.append(_issue("checksum_mismatch", rel, "content differs from SHA256SUMS"))

    tables = load_tables(snapshot)
    for name, columns in SCHEMAS.items():
        missing = [c for c in columns if c not in tables[name].columns]
        if missing:
            issues.append(_issue("missing_columns", name, f"missing columns {missing}"))
    if any(i["code"] == "missing_columns" for i in issues):
        return issues

    control = cfg["design"]["control_group"]
    pages = tables["pages.csv"]
    known_groups = {"technical", "content", "local", "accessibility", control}
    if pages["page"].duplicated().any():
        issues.append(_issue("duplicate_key", "pages.csv", "page ids must be unique"))
    unknown_groups = sorted(set(pages["design_group"]) - known_groups)
    if unknown_groups:
        issues.append(_issue("unknown_design_group", "pages.csv", f"{unknown_groups}"))
    page_ids = set(pages["page"])
    group_of = dict(zip(pages["page"], pages["design_group"]))

    gsc = tables["gsc_daily.csv"]
    name = "gsc_daily.csv"
    if _bad_dates(gsc["date"]).any():
        issues.append(_issue("bad_date", name, f"{int(_bad_dates(gsc['date']).sum())} rows"))
    for column in ("clicks", "impressions"):
        values = pd.to_numeric(gsc[column], errors="coerce")
        bad = values.isna() | (values < 0) | (values % 1 != 0)
        if bad.any():
            issues.append(_issue("negative_or_non_integer", name, f"{column}: {int(bad.sum())} rows"))
    clicks = pd.to_numeric(gsc["clicks"], errors="coerce")
    impressions = pd.to_numeric(gsc["impressions"], errors="coerce")
    position = pd.to_numeric(gsc["position"], errors="coerce")
    if (clicks > impressions).any():
        issues.append(_issue("clicks_gt_impressions", name, f"{int((clicks > impressions).sum())} rows"))
    bad_position = (impressions > 0) & (position.isna() | (position < 1))
    if bad_position.any():
        issues.append(_issue("position_out_of_range", name, f"{int(bad_position.sum())} rows"))
    orphan_position = (impressions == 0) & position.notna()
    if orphan_position.any():
        issues.append(_issue("position_without_impressions", name, f"{int(orphan_position.sum())} rows"))
    if gsc.duplicated(["date", "page", "segment"]).any():
        issues.append(_issue("duplicate_key", name, "date/page/segment must be unique"))
    unknown_pages = sorted(set(gsc["page"]) - page_ids)
    if unknown_pages:
        issues.append(_issue("unknown_page", name, f"{unknown_pages[:5]}"))
    unknown_segments = sorted(set(gsc["segment"]) - {"local", "general"})
    if unknown_segments:
        issues.append(_issue("unknown_segment", name, f"{unknown_segments}"))

    interventions = tables["interventions.csv"]
    name = "interventions.csv"
    if interventions["intervention_id"].duplicated().any():
        issues.append(_issue("duplicate_key", name, "intervention_id must be unique"))
    if _bad_dates(interventions["date"]).any():
        issues.append(_issue("bad_date", name, "unparseable dates"))
    unknown_types = sorted(set(interventions["type"]) - {"technical", "content", "local",
                                                          "accessibility", "links"})
    if unknown_types:
        issues.append(_issue("unknown_type", name, f"{unknown_types}"))
    for row in interventions.itertuples():
        if row.type in SITE_WIDE_TYPES:
            if row.page != "*":
                issues.append(_issue("site_wide_page", name, f"{row.intervention_id}: use page '*'"))
            continue
        if row.page not in page_ids:
            issues.append(_issue("unknown_page", name, f"{row.intervention_id}: {row.page}"))
        elif group_of[row.page] == control:
            issues.append(_issue("control_page_intervened", name, f"{row.intervention_id}: {row.page}"))
        elif group_of[row.page] != row.type:
            issues.append(_issue("type_group_mismatch", name,
                                 f"{row.intervention_id}: {row.type} on {group_of[row.page]} page"))

    lighthouse = tables["lighthouse.csv"]
    name = "lighthouse.csv"
    for column in ("performance", "accessibility", "seo"):
        values = pd.to_numeric(lighthouse[column], errors="coerce")
        if (values.isna() | (values < 0) | (values > 100)).any():
            issues.append(_issue("score_out_of_range", name, f"{column} must be within 0..100"))
    if not set(lighthouse["snapshot"]) <= {"before", "after"}:
        issues.append(_issue("unknown_snapshot", name, "snapshot must be before/after"))

    authority = tables["authority.csv"]
    if _bad_dates(authority["date"]).any():
        issues.append(_issue("bad_date", "authority.csv", "unparseable dates"))
    if pd.to_numeric(authority["value"], errors="coerce").isna().any():
        issues.append(_issue("non_numeric", "authority.csv", "value must be numeric"))

    for label in ("before", "after"):
        name = f"crawl/{label}/index.csv"
        index = tables[name]
        for row in index.itertuples():
            if isinstance(row.file, str) and row.file and not (snapshot / "crawl" / label / row.file).is_file():
                issues.append(_issue("missing_file", name, f"{row.file}"))

    treated_pages = interventions[~interventions["type"].isin(SITE_WIDE_TYPES)]
    n_control = int((pages["design_group"] == control).sum())
    for hyp in cfg["hypotheses"]:
        if hyp["kind"] == "descriptive":
            continue
        needed = [hyp["intervention"]] + ([hyp["compare_to"]] if hyp["kind"] == "did_difference" else [])
        for kind in needed:
            n = treated_pages.loc[treated_pages["type"] == kind, "page"].nunique()
            if n < 2:
                issues.append(_issue("too_few_pages", "interventions.csv",
                                     f"{hyp['id']}: {kind} has {n} treated pages (need >= 2)"))
        if n_control < 2:
            issues.append(_issue("too_few_pages", "pages.csv", f"{hyp['id']}: control has {n_control} pages"))
    return issues


def normalized_gsc(tables: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (segment-level, page-level) daily panels with impression-weighted position."""
    gsc = tables["gsc_daily.csv"].copy()
    gsc["clicks"] = gsc["clicks"].astype(np.int64)
    gsc["impressions"] = gsc["impressions"].astype(np.int64)
    gsc["position"] = pd.to_numeric(gsc["position"], errors="coerce")
    segment = gsc.sort_values(["date", "page", "segment"]).reset_index(drop=True)
    weighted = segment.assign(weight=segment["position"].fillna(0) * segment["impressions"])
    page = weighted.groupby(["date", "page"], as_index=False).agg(
        clicks=("clicks", "sum"), impressions=("impressions", "sum"), weight=("weight", "sum"))
    page["position"] = np.where(page["impressions"] > 0,
                                page["weight"] / page["impressions"].where(page["impressions"] > 0, 1),
                                np.nan)
    page = page.drop(columns="weight").sort_values(["date", "page"]).reset_index(drop=True)
    return segment, page
