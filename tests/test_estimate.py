import math

import numpy as np
import pandas as pd
import pytest

from conftest import SMOKE_CONFIG
from research.config import load_config
from research.design import build_design
from research.estimate import (bootstrap_draws, build_predictions, compute_page_windows, decide, effect_transform,
                               expected_ctr, fit_ctr_curve, point_effect, rng_for)

DAYS = pd.date_range("2026-04-01", "2026-09-07").strftime("%Y-%m-%d")
T = "2026-06-22"


def _panel(values: dict[str, tuple[float, float]], column: str, base: dict | None = None, segment=None):
    rows = []
    for page, (pre, post) in values.items():
        for day in DAYS:
            row = {"date": day, "page": page, "clicks": 50, "impressions": 1000, "position": 5.0}
            row.update(base or {})
            row[column] = pre if day < T else post
            if segment:
                row["segment"] = segment
            rows.append(row)
    return pd.DataFrame(rows)


def _setup(hypothesis, groups, interventions):
    cfg = load_config(SMOKE_CONFIG, {"hypotheses": [hypothesis]})
    pages = pd.DataFrame({"page": list(groups), "url": list(groups), "design_group": list(groups.values())})
    frame = pd.DataFrame([{"intervention_id": f"I{i}", "page": p, "type": kind, "date": d, "description": ""}
                          for i, (p, kind, d) in enumerate(interventions)])
    return cfg, build_design(cfg, pages, frame)


H1 = {"id": "H1", "kind": "did", "intervention": "technical", "metric": "position", "segment": "all", "threshold": 0.2}
GROUPS = {"T1": "technical", "T2": "technical", "C1": "control", "C2": "control"}
TREATED = [("T1", "technical", T), ("T2", "technical", T)]


def test_position_did_matches_hand_calculation():
    cfg, design = _setup(H1, GROUPS, TREATED)
    panel = _panel({"T1": (10, 7), "T2": (20, 12), "C1": (8, 8.8), "C2": (16, 17.6)}, "position")
    curve = fit_ctr_curve(panel, "2026-06-15", "2026-09-07")
    windows = compute_page_windows(cfg, design, panel, panel.iloc[0:0], curve)
    expected_did = 1 - math.sqrt(0.7 * 0.6) / 1.1
    expected_naive = 1 - math.sqrt(0.7 * 0.6)
    did = build_predictions(cfg, H1, windows, design, "did", "r")
    naive = build_predictions(cfg, H1, windows, design, "naive_prepost", "r")
    assert point_effect(H1, did, "position") == pytest.approx(expected_did, abs=1e-12)
    assert point_effect(H1, naive, "position") == pytest.approx(expected_naive, abs=1e-12)
    draws = bootstrap_draws(H1, windows, "did", 400, rng_for(1, "H1"))
    # Control changes are identical, so a draw depends only on which treated pages were resampled:
    # both T1, both T2, or one of each.
    possible = {round(1 - 0.7 / 1.1, 10), round(1 - 0.6 / 1.1, 10), round(expected_did, 10)}
    assert set(np.round(draws, 10)) == possible


def test_adjusted_ctr_ignores_position_and_detects_click_doubling():
    hyp = {**H1, "id": "H2", "intervention": "technical", "metric": "ctr_adjusted"}
    cfg, design = _setup(hyp, GROUPS, TREATED)
    panel = _panel({"T1": (5000, 10000), "T2": (4000, 8000), "C1": (5000, 5000), "C2": (3000, 3000)}, "clicks",
                   base={"impressions": 100000})
    curve = fit_ctr_curve(panel, "2026-06-15", "2026-09-07")
    windows = compute_page_windows(cfg, design, panel, panel.iloc[0:0], curve)
    predictions = build_predictions(cfg, hyp, windows, design, "did", "r")
    assert point_effect(hyp, predictions, "ctr_adjusted") == pytest.approx(1.0, abs=1e-3)


def test_difference_of_two_arms_on_local_segment():
    hyp = {"id": "H3", "kind": "did_difference", "intervention": "local", "compare_to": "content",
           "metric": "clicks", "segment": "local", "threshold": 0.0}
    groups = {"L1": "local", "L2": "local", "K1": "content", "K2": "content", "C1": "control", "C2": "control"}
    cfg, design = _setup(hyp, groups, [("L1", "local", T), ("L2", "local", T), ("K1", "content", T),
                                       ("K2", "content", T)])
    segment = _panel({"L1": (4000, 8000), "L2": (2000, 4000), "K1": (4000, 6000), "K2": (2000, 3000),
                      "C1": (3000, 3000), "C2": (1000, 1000)}, "clicks", base={"impressions": 100000},
                     segment="local")
    windows = compute_page_windows(cfg, design, segment.iloc[0:0], segment, fit_ctr_curve(segment, T, "2026-09-07"))
    predictions = build_predictions(cfg, hyp, windows, design, "did", "r")
    assert point_effect(hyp, predictions, "clicks") == pytest.approx(1.0 - 0.5, abs=1e-3)


def test_ctr_curve_uses_only_rows_before_training_end():
    panel = _panel({"P1": (0.05, 0.9)}, "position", base={"clicks": 10, "impressions": 100})
    panel["position"] = np.where(panel["date"] < T, 3.0, 3.0)
    changed = panel.assign(clicks=np.where(panel["date"] >= "2026-06-15", 100, panel["clicks"]))
    assert fit_ctr_curve(panel, "2026-06-15", "2026-09-07") == fit_ctr_curve(changed, "2026-06-15", "2026-09-07")


def test_expected_ctr_bins():
    curve = {"edges": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 30], "ctr": list(range(13))}
    assert expected_ctr(curve, [1, 1.5, 9.99, 10, 14.9, 35]).tolist() == [0, 0, 8, 9, 9, 12]


def test_effect_sign_and_decision_rule():
    assert effect_transform(math.log(0.8), "position") == pytest.approx(0.2)
    assert effect_transform(math.log(1.3), "clicks") == pytest.approx(0.3)
    assert decide(0.21, 0.40, 0.20) == "podprta"
    assert decide(-0.10, 0.19, 0.20) == "ni podprta"
    assert decide(0.10, 0.30, 0.20) == "neodločeno"


def test_too_few_days_excludes_page_from_every_model():
    cfg, design = _setup(H1, GROUPS, TREATED)
    panel = _panel({"T1": (10, 7), "T2": (20, 12), "C1": (8, 8.8), "C2": (16, 17.6)}, "position")
    panel = panel[~((panel["page"] == "T2") & (panel["date"] >= "2026-07-06"))]
    windows = compute_page_windows(cfg, design, panel, panel.iloc[0:0], fit_ctr_curve(panel, T, "2026-09-07"))
    for model in ("did", "naive_prepost"):
        assert set(build_predictions(cfg, H1, windows, design, model, "r")["page"]) == {"T1"}
