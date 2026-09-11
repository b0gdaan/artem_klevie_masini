import shutil
from datetime import date, timedelta

import pandas as pd
import pytest

from conftest import SMOKE_CONFIG, SMOKE_SNAPSHOT
from research.config import load_config
from research.data import available_until, load_tables, normalized_gsc, validate_snapshot
from research.design import build_design, ctr_training_end
from research.estimate import compute_page_windows, fit_ctr_curve
from research.io_utils import atomic_write_text, format_sha256sums, tree_sha256, write_csv

H1 = [{"id": "H1", "kind": "did", "intervention": "technical", "metric": "position", "segment": "all",
       "threshold": 0.2}]


def _copy(tmp_path):
    target = tmp_path / "snapshot"
    shutil.copytree(SMOKE_SNAPSHOT, target)
    return target


def _reseal(snapshot):
    _, files = tree_sha256(snapshot)
    atomic_write_text(snapshot / "SHA256SUMS", format_sha256sums(files))


def _codes(snapshot):
    return {issue["code"] for issue in validate_snapshot(snapshot, load_config(SMOKE_CONFIG))}


def test_committed_smoke_snapshot_is_valid():
    assert _codes(SMOKE_SNAPSHOT) == set()


@pytest.mark.parametrize("mutation, code", [
    (lambda g: g.assign(clicks=g["clicks"].where(g.index != 0, g.loc[0, "impressions"] + 1)), "clicks_gt_impressions"),
    (lambda g: pd.concat([g, g.iloc[[0]]]), "duplicate_key"),
    (lambda g: g.assign(impressions=g["impressions"].where(g.index != 3, -1)), "negative_or_non_integer"),
    (lambda g: g.assign(page=g["page"].where(g.index != 5, "P99")), "unknown_page"),
    (lambda g: g.assign(position=g["position"].where(g.index != 7, 0.5)), "position_out_of_range"),
    (lambda g: g.assign(segment=g["segment"].where(g.index != 9, "brand")), "unknown_segment"),
])
def test_validation_detects_damaged_search_console_rows(tmp_path, mutation, code):
    snapshot = _copy(tmp_path)
    gsc = pd.read_csv(snapshot / "gsc_daily.csv", dtype={"date": str, "page": str, "segment": str})
    write_csv(snapshot / "gsc_daily.csv", mutation(gsc))
    _reseal(snapshot)
    assert code in _codes(snapshot)


def test_validation_detects_intervention_on_control_page(tmp_path):
    snapshot = _copy(tmp_path)
    frame = pd.read_csv(snapshot / "interventions.csv", dtype=str)
    frame.loc[0, "page"] = "P25"
    write_csv(snapshot / "interventions.csv", frame)
    _reseal(snapshot)
    assert "control_page_intervened" in _codes(snapshot)


def test_validation_detects_unsealed_change(tmp_path):
    snapshot = _copy(tmp_path)
    path = snapshot / "authority.csv"
    path.write_bytes(path.read_bytes().replace(b",17\n", b",18\n"))
    assert "checksum_mismatch" in _codes(snapshot)


def _tiny_design(cfg):
    pages = pd.DataFrame({"page": ["T1", "T2", "C1", "C2"], "url": ["u1", "u2", "u3", "u4"],
                          "design_group": ["technical", "technical", "control", "control"]})
    interventions = pd.DataFrame({"intervention_id": ["I1", "I2"], "page": ["T1", "T2"], "type": "technical",
                                  "date": "2026-06-22", "description": ""})
    return pages, interventions


def test_windows_are_computed_from_intervention_date():
    cfg = load_config(SMOKE_CONFIG, {"hypotheses": H1})
    design = build_design(cfg, *_tiny_design(cfg))
    t1 = design[design["page"] == "T1"].set_index("period")
    assert (t1.loc["pre", "start"], t1.loc["pre", "end"]) == ("2026-05-04", "2026-06-15")
    assert (t1.loc["post", "start"], t1.loc["post", "end"]) == ("2026-07-06", "2026-08-17")
    treated = set(design.loc[design["role"] == "treated", "page"])
    control = set(design.loc[design["role"] == "control", "page"])
    assert treated == {"T1", "T2"} and control == {"C1", "C2"} and not treated & control


def test_post_window_is_truncated_at_label_availability():
    cfg = load_config(SMOKE_CONFIG, {"hypotheses": H1, "data": {"analysis_cutoff": "2026-08-01"}})
    design = build_design(cfg, *_tiny_design(cfg))
    post = design[design["period"] == "post"]
    assert available_until(cfg) == "2026-07-29"
    assert post["end"].eq("2026-07-30").all()
    assert post["post_days_effective"].eq(24).all() and not post["window_eligible"].any()


def test_placebo_windows_end_before_real_pre_intervention_buffer():
    cfg = load_config(SMOKE_CONFIG, {"hypotheses": H1})
    placebo = build_design(cfg, *_tiny_design(cfg), placebo_shift_days=63)
    assert placebo["end"].max() <= (date(2026, 6, 22) - timedelta(days=7)).isoformat()


def _windows(cfg, panel_page, panel_segment, tables):
    design = build_design(cfg, tables["pages.csv"], tables["interventions.csv"])
    curve = fit_ctr_curve(panel_page, ctr_training_end(tables["interventions.csv"], cfg), available_until(cfg))
    return curve, compute_page_windows(cfg, design, panel_page, panel_segment, curve)


def test_rows_after_label_availability_change_nothing():
    cfg = load_config(SMOKE_CONFIG)
    tables = load_tables(SMOKE_SNAPSHOT)
    segment, page = normalized_gsc(tables)
    curve, windows = _windows(cfg, page, segment, tables)
    last = page[page["date"] == page["date"].max()]
    future_page = pd.concat([page] + [last.assign(date=(date(2026, 9, 8) + timedelta(days=i)).isoformat(),
                                                  clicks=999, impressions=1000, position=1.0) for i in range(10)])
    last_segment = segment[segment["date"] == segment["date"].max()]
    future_segment = pd.concat([segment] + [last_segment.assign(date=(date(2026, 9, 8) + timedelta(days=i)).isoformat(),
                                                                clicks=999, impressions=1000, position=1.0)
                                            for i in range(10)])
    future_curve, future_windows = _windows(cfg, future_page, future_segment, tables)
    assert future_curve == curve
    pd.testing.assert_frame_equal(future_windows, windows)


def test_changes_after_training_boundary_leave_curve_and_earlier_windows_intact():
    cfg = load_config(SMOKE_CONFIG)
    tables = load_tables(SMOKE_SNAPSHOT)
    segment, page = normalized_gsc(tables)
    boundary = ctr_training_end(tables["interventions.csv"], cfg)
    curve, windows = _windows(cfg, page, segment, tables)
    later = page["date"] >= boundary
    changed = page.assign(clicks=page["clicks"].where(~later, page["impressions"]),
                          position=page["position"].where(~later, page["position"] * 2))
    changed_curve, changed_windows = _windows(cfg, changed, segment, tables)
    assert changed_curve == curve
    h1 = (windows["hypothesis_id"] == "H1")
    pre = h1 & (windows["period"] == "pre")
    pd.testing.assert_frame_equal(changed_windows[pre], windows[pre])
    post = h1 & (windows["period"] == "post")
    assert not changed_windows.loc[post, "value"].equals(windows.loc[post, "value"])
