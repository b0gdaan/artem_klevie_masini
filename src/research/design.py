"""Pre/post windows, treated/control roles and label availability.

Windows are half-open ``[start, end)`` ISO dates. For an intervention on date T:

* pre  = [T - buffer - pre_days, T - buffer)
* post = [T + ramp, T + ramp + post_days), truncated at the last date whose
  Search Console values are final at the analysis cutoff.

Nothing after ``available_until`` enters any window, so later data cannot change
an estimate issued at the cutoff.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from .config import arms
from .data import SITE_WIDE_TYPES, available_until

DESIGN_COLUMNS = ["hypothesis_id", "arm", "window_key", "page", "role", "period", "start", "end",
                  "intervention_date", "label_cutoff", "post_days_effective", "window_eligible"]


def _iso(day: date) -> str:
    return day.isoformat()


def intervention_dates(interventions: pd.DataFrame, kind: str) -> dict[str, str]:
    rows = interventions[interventions["type"] == kind]
    return rows.groupby("page")["date"].min().to_dict()


def ctr_training_end(interventions: pd.DataFrame, cfg: dict) -> str:
    """Exclusive end of the pre-intervention period used to fit the expected-CTR curve."""
    first = date.fromisoformat(interventions["date"].min())
    return _iso(first - timedelta(days=cfg["design"]["buffer_days"]))


def build_design(cfg: dict, pages: pd.DataFrame, interventions: pd.DataFrame,
                 placebo_shift_days: int = 0) -> pd.DataFrame:
    design_cfg = cfg["design"]
    avail = date.fromisoformat(available_until(cfg))
    controls = sorted(pages.loc[pages["design_group"] == design_cfg["control_group"], "page"])
    page_level = interventions[~interventions["type"].isin(SITE_WIDE_TYPES)]
    rows = []
    for hyp in cfg["hypotheses"]:
        if hyp["kind"] == "descriptive":
            continue
        for arm, kind in arms(hyp).items():
            dates = intervention_dates(page_level, kind)
            for window_key in sorted(set(dates.values())):
                real = date.fromisoformat(window_key)
                anchor = real - timedelta(days=placebo_shift_days)
                pre_start = anchor - timedelta(days=design_cfg["buffer_days"] + design_cfg["pre_days"])
                pre_end = anchor - timedelta(days=design_cfg["buffer_days"])
                post_start = anchor + timedelta(days=design_cfg["ramp_days"])
                post_end = min(post_start + timedelta(days=design_cfg["post_days"]),
                               avail + timedelta(days=1))
                if placebo_shift_days:
                    # A placebo post window must end before the real pre-intervention buffer.
                    post_end = min(post_end, real - timedelta(days=design_cfg["buffer_days"]))
                effective = max((post_end - post_start).days, 0)
                eligible = effective >= design_cfg["min_post_days"]
                treated = sorted(p for p, d in dates.items() if d == window_key)
                for role, members in (("treated", treated), ("control", controls)):
                    for page in members:
                        for period, start, end in (("pre", pre_start, pre_end),
                                                   ("post", post_start, max(post_end, post_start))):
                            rows.append({
                                "hypothesis_id": hyp["id"], "arm": arm, "window_key": window_key,
                                "page": page, "role": role, "period": period,
                                "start": _iso(start), "end": _iso(end),
                                "intervention_date": _iso(anchor), "label_cutoff": _iso(avail),
                                "post_days_effective": effective, "window_eligible": eligible,
                            })
    frame = pd.DataFrame(rows, columns=DESIGN_COLUMNS)
    return frame.sort_values(["hypothesis_id", "arm", "window_key", "role", "page", "period"]
                             ).reset_index(drop=True)
