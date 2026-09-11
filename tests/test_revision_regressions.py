import math

import pandas as pd
import pytest

from research.estimate import window_value
from research.release import release_run


def test_position_window_is_weighted_by_impressions():
    rows = pd.DataFrame({"position": [2., 10.], "impressions": [90, 10], "clicks": [9, 1]})
    count, value = window_value(rows, "position", "2026-01-01", "2026-01-03", {})
    assert count == 2
    assert value == pytest.approx(math.log(2.8))


def test_click_eligibility_counts_only_days_with_impressions():
    rows = pd.DataFrame({"impressions": [100, 0], "clicks": [10, 0]})
    count, value = window_value(rows, "clicks", "2026-01-01", "2026-01-03", {})
    assert count == 1
    assert value == pytest.approx(math.log(10.5 / 2))


def test_release_refuses_skipped_suite(tmp_path, smoke_run):
    junit = tmp_path / "skipped.xml"
    junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="1">'
                     '<testcase name="required"><skipped/></testcase></testsuite>', encoding="utf-8")
    code, out, problems = release_run(smoke_run, junit, tmp_path / "release")
    assert code == 1 and out is None
    assert any("required tests skipped" in problem for problem in problems)
