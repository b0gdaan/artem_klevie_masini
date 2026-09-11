"""Window statistics, difference-in-differences predictions and bootstrap inference.

For each page and window the statistic is on the log scale:

* position      mean of log(position) over days with impressions;
* clicks        log((clicks + 0.5) / calendar days);
* ctr_adjusted  log((clicks + 0.5) / (expected clicks + 0.5)), where expected
                clicks come from a CTR-by-position curve fitted only on data
                before the first intervention;
* ctr_raw       log((clicks + 0.5) / (impressions + 0.5)), used in the ablation.

The counterfactual for a treated page is ``pre + mean control change`` (model
``did``) or just ``pre`` (ablation ``naive_prepost``). The effect is
``mean(target - prediction)`` transformed back to a relative change, so it can
always be recomputed from the saved predictions.

Uncertainty: pages are resampled with replacement (treated and control pages
separately). Resampling whole pages keeps each page's day-to-day dependence
intact; it is a cluster bootstrap over pages.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .config import arms, inferential

MODEL_VERSION = "did-v1"
CTR_EDGES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 30]
PAGE_WINDOW_COLUMNS = ["hypothesis_id", "arm", "window_key", "page", "role", "period", "metric",
                       "n_days", "value", "eligible"]
PREDICTION_COLUMNS = ["run_id", "hypothesis_id", "model", "model_version", "arm", "window_key", "page",
                      "role", "split", "target_name", "target", "prediction", "issued_at",
                      "intervention_date", "target_start", "target_end", "label_cutoff"]
PREDICTION_KEY = ["run_id", "hypothesis_id", "model", "arm", "window_key", "page"]
DECISION_SUPPORTED = "podprta"
DECISION_REJECTED = "ni podprta"
DECISION_UNDECIDED = "neodločeno"
DECISION_NO_DATA = "ni dovolj podatkov"


def models_for(hyp: dict) -> list[str]:
    models = ["did", "naive_prepost"]
    if hyp["metric"] == "ctr_adjusted":
        models.append("did_raw_ctr")
    return models


def model_metric(hyp: dict, model: str) -> str:
    return "ctr_raw" if model == "did_raw_ctr" else hyp["metric"]


def rng_for(seed: int, *keys: str) -> np.random.Generator:
    digest = hashlib.sha256("|".join(keys).encode("utf-8")).hexdigest()
    return np.random.default_rng([seed, int(digest[:8], 16)])


def effect_transform(mean_log_diff, metric: str):
    """Relative change; for position a positive value means a better (lower) position."""
    if metric == "position":
        return -np.expm1(mean_log_diff)
    return np.expm1(mean_log_diff)


def metric_frame(panel_page: pd.DataFrame, panel_segment: pd.DataFrame, segment: str) -> pd.DataFrame:
    if segment == "all":
        return panel_page
    return panel_segment[panel_segment["segment"] == segment][
        ["date", "page", "clicks", "impressions", "position"]]


def fit_ctr_curve(panel_page: pd.DataFrame, train_end: str, available_until: str) -> dict:
    rows = panel_page[(panel_page["date"] < train_end) & (panel_page["date"] <= available_until)
                      & (panel_page["impressions"] > 0)]
    n_bins = len(CTR_EDGES)
    bins = np.clip(np.digitize(rows["position"].to_numpy(), CTR_EDGES) - 1, 0, n_bins - 1)
    clicks = np.bincount(bins, weights=rows["clicks"].to_numpy(dtype=float), minlength=n_bins)
    impressions = np.bincount(bins, weights=rows["impressions"].to_numpy(dtype=float), minlength=n_bins)
    ctr = pd.Series(np.where(impressions > 0, clicks / np.maximum(impressions, 1), np.nan))
    overall = clicks.sum() / impressions.sum() if impressions.sum() else 0.0
    ctr = ctr.ffill().bfill().fillna(overall)
    return {
        "model_version": "ctr-bins-v1",
        "edges": CTR_EDGES,
        "ctr": [round(float(v), 12) for v in ctr],
        "impressions": [int(v) for v in impressions],
        "train_end_exclusive": train_end,
        "available_until": available_until,
        "training_rows": int(len(rows)),
    }


def expected_ctr(curve: dict, positions) -> np.ndarray:
    index = np.clip(np.digitize(np.asarray(positions, dtype=float), curve["edges"]) - 1,
                    0, len(curve["ctr"]) - 1)
    return np.asarray(curve["ctr"])[index]


def window_value(rows: pd.DataFrame, metric: str, start: str, end: str, curve: dict) -> tuple[int, float]:
    if metric == "clicks":
        calendar_days = (date.fromisoformat(end) - date.fromisoformat(start)).days
        if len(rows) == 0 or calendar_days <= 0:
            return 0, np.nan
        return len(rows), float(np.log((rows["clicks"].sum() + 0.5) / calendar_days))
    shown = rows[rows["impressions"] > 0]
    if len(shown) == 0:
        return 0, np.nan
    if metric == "position":
        return len(shown), float(np.log(shown["position"].to_numpy()).mean())
    clicks = shown["clicks"].sum() + 0.5
    if metric == "ctr_adjusted":
        expected = float((shown["impressions"].to_numpy() * expected_ctr(curve, shown["position"])).sum())
        return len(shown), float(np.log(clicks / (expected + 0.5)))
    if metric == "ctr_raw":
        return len(shown), float(np.log(clicks / (shown["impressions"].sum() + 0.5)))
    raise ValueError(f"unknown metric {metric}")


def compute_page_windows(cfg: dict, design: pd.DataFrame, panel_page: pd.DataFrame,
                         panel_segment: pd.DataFrame, curve: dict) -> pd.DataFrame:
    rows = []
    main_metric = {}
    for hyp in inferential(cfg):
        main_metric[hyp["id"]] = hyp["metric"]
        frame = metric_frame(panel_page, panel_segment, hyp.get("segment", "all"))
        by_page = {page: group for page, group in frame.groupby("page")}
        metrics = list(dict.fromkeys(model_metric(hyp, m) for m in models_for(hyp)))
        for spec in design[design["hypothesis_id"] == hyp["id"]].itertuples(index=False):
            group = by_page.get(spec.page)
            if group is None:
                selected = frame.iloc[0:0]
            else:
                selected = group[(group["date"] >= spec.start) & (group["date"] < spec.end)
                                 & (group["date"] <= spec.label_cutoff)]
            for metric in metrics:
                n_days, value = window_value(selected, metric, spec.start, spec.end, curve)
                rows.append({"hypothesis_id": spec.hypothesis_id, "arm": spec.arm,
                             "window_key": spec.window_key, "page": spec.page, "role": spec.role,
                             "period": spec.period, "metric": metric, "n_days": n_days, "value": value,
                             "window_eligible": bool(spec.window_eligible)})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=PAGE_WINDOW_COLUMNS)

    keys = ["hypothesis_id", "arm", "window_key", "page", "role"]
    main = frame[frame["metric"] == frame["hypothesis_id"].map(main_metric)]
    status = main.groupby(keys, as_index=False).agg(min_days=("n_days", "min"),
                                                    window_eligible=("window_eligible", "all"))
    status["ok"] = (status["min_days"] >= cfg["design"]["min_days_per_window"]) & status["window_eligible"]
    controls = status[(status["role"] == "control") & status["window_eligible"]]
    control_ok = controls.groupby(["hypothesis_id", "page"])["ok"].all()
    status["eligible"] = np.where(
        status["role"] == "treated", status["ok"],
        status["window_eligible"].to_numpy() & np.array([bool(control_ok.get((h, p), False))
                                                         for h, p in zip(status["hypothesis_id"], status["page"])]))
    frame = frame.merge(status[keys + ["eligible"]], on=keys, how="left")
    frame["eligible"] = frame["eligible"].astype(bool)
    return frame[PAGE_WINDOW_COLUMNS].sort_values(
        ["hypothesis_id", "metric", "arm", "window_key", "role", "page", "period"]).reset_index(drop=True)


def _wide(page_windows: pd.DataFrame, hyp: dict, metric: str) -> pd.DataFrame:
    selected = page_windows[(page_windows["hypothesis_id"] == hyp["id"])
                            & (page_windows["metric"] == metric) & page_windows["eligible"]]
    if selected.empty:
        return pd.DataFrame(columns=["arm", "window_key", "page", "role", "pre", "post", "delta"])
    wide = selected.pivot_table(index=["arm", "window_key", "page", "role"], columns="period",
                                values="value", aggfunc="first").reset_index()
    wide.columns.name = None
    wide = wide.dropna(subset=["pre", "post"])
    wide["delta"] = wide["post"] - wide["pre"]
    return wide


def build_predictions(cfg: dict, hyp: dict, page_windows: pd.DataFrame, design: pd.DataFrame,
                      model: str, run_id: str) -> pd.DataFrame:
    metric = model_metric(hyp, model)
    wide = _wide(page_windows, hyp, metric)
    controls = wide[wide["role"] == "control"]
    if wide.empty or controls.empty:
        return pd.DataFrame(columns=PREDICTION_COLUMNS)
    control_delta = controls.groupby(["arm", "window_key"], as_index=False)["delta"].mean()
    treated = wide[wide["role"] == "treated"].merge(
        control_delta.rename(columns={"delta": "control_delta"}), on=["arm", "window_key"], how="inner")
    treated["prediction"] = treated["pre"] if model == "naive_prepost" else treated["pre"] + treated["control_delta"]
    windows = design[(design["hypothesis_id"] == hyp["id"]) & (design["role"] == "treated")
                     & (design["period"] == "post")][
        ["arm", "window_key", "page", "start", "end", "label_cutoff", "intervention_date"]]
    result = treated.merge(windows, on=["arm", "window_key", "page"], how="left")
    result = result.assign(
        run_id=run_id, hypothesis_id=hyp["id"], model=model, model_version=MODEL_VERSION, role="treated",
        split="post", target_name=f"log_{metric}", target=result["post"],
        issued_at=cfg["data"]["analysis_cutoff"], target_start=result["start"], target_end=result["end"])
    return result[PREDICTION_COLUMNS].sort_values(PREDICTION_KEY).reset_index(drop=True)


def point_effect(hyp: dict, predictions: pd.DataFrame, metric: str) -> float:
    effects = {arm: float(effect_transform((group["target"] - group["prediction"]).mean(), metric))
               for arm, group in predictions.groupby("arm")}
    if hyp["kind"] == "did_difference":
        return effects["a"] - effects["b"]
    return effects["a"]


def bootstrap_draws(hyp: dict, page_windows: pd.DataFrame, model: str, reps: int,
                    rng: np.random.Generator) -> np.ndarray:
    metric = model_metric(hyp, model)
    wide = _wide(page_windows, hyp, metric)
    control = wide[wide["role"] == "control"].pivot_table(
        index="page", columns=["arm", "window_key"], values="delta", aggfunc="first").dropna()
    matrix = control.to_numpy()
    column = {key: i for i, key in enumerate(control.columns)}
    control_index = rng.integers(0, len(matrix), size=(reps, len(matrix)))
    control_means = matrix[control_index].mean(axis=1)
    effects = {}
    for arm in sorted(arms(hyp)):
        treated = wide[(wide["role"] == "treated") & (wide["arm"] == arm)]
        deltas = treated["delta"].to_numpy()
        columns = np.array([column[(arm, key)] for key in treated["window_key"]])
        index = rng.integers(0, len(deltas), size=(reps, len(deltas)))
        if model == "naive_prepost":
            mean_diff = deltas[index].mean(axis=1)
        else:
            mean_diff = (deltas[index] - control_means[np.arange(reps)[:, None], columns[index]]).mean(axis=1)
        effects[arm] = effect_transform(mean_diff, metric)
    return effects["a"] - effects["b"] if hyp["kind"] == "did_difference" else effects["a"]


def decide(low: float, high: float, threshold: float) -> str:
    if low >= threshold:
        return DECISION_SUPPORTED
    if high < threshold:
        return DECISION_REJECTED
    return DECISION_UNDECIDED


def describe_authority(cfg: dict, hyp: dict, authority: pd.DataFrame, interventions: pd.DataFrame,
                       available_until: str) -> dict:
    start = interventions.loc[interventions["type"] == hyp["intervention"], "date"].min()
    series = authority[(authority["metric"] == hyp["metric"]) & (authority["date"] <= available_until)]
    series = series.assign(value=pd.to_numeric(series["value"])).sort_values("date")
    horizon_end = (date.fromisoformat(start) + timedelta(days=hyp["horizon_days"])).isoformat()
    baseline = series[series["date"] <= start]
    observed = series[series["date"] <= min(horizon_end, available_until)]
    if baseline.empty or observed.empty:
        return {"estimate": np.nan, "decision": DECISION_NO_DATA, "status": "insufficient_data",
                "note": "no authority value before the link-building start"}
    change = float(observed["value"].iloc[-1] - baseline["value"].iloc[-1])
    complete = available_until >= horizon_end
    if change >= hyp["threshold"]:
        decision = "prag dosežen (opisno)"
    elif complete:
        decision = "prag ni dosežen (opisno)"
    else:
        decision = "neodločeno – obdobje še traja"
    return {"estimate": change, "decision": decision, "status": "descriptive",
            "note": (f"baseline {baseline['date'].iloc[-1]}={baseline['value'].iloc[-1]:g}; "
                     f"last {observed['date'].iloc[-1]}={observed['value'].iloc[-1]:g}; "
                     f"horizon ends {horizon_end}; complete={complete}")}


def evaluate(cfg: dict, page_windows: pd.DataFrame, predictions: pd.DataFrame, tables: dict,
             run_id: str, models: tuple[str, ...], available_until: str, tag: str = "") -> pd.DataFrame:
    inference = cfg["inference"]
    level = float(inference["ci_level"])
    tests = max(len(inferential(cfg)), 1)
    level_adj = 1 - (1 - level) / tests if inference["multiplicity"] == "bonferroni" else level
    reps = int(inference["bootstrap_reps"])
    rows = []
    for hyp in cfg["hypotheses"]:
        base = {"run_id": run_id, "hypothesis_id": hyp["id"], "kind": hyp["kind"], "metric": hyp["metric"],
                "segment": hyp.get("segment", "all"), "intervention": hyp["intervention"],
                "compare_to": hyp.get("compare_to", ""), "threshold": hyp["threshold"],
                "model_version": MODEL_VERSION, "ci_level": level, "ci_level_adj": level_adj,
                "bootstrap_reps": reps}
        if hyp["kind"] == "descriptive":
            if "did" in models:
                described = describe_authority(cfg, hyp, tables["authority.csv"], tables["interventions.csv"],
                                               available_until)
                rows.append({**base, "model": "descriptive", "estimate": described["estimate"],
                             "decision": described["decision"], "decision_unadjusted": described["decision"],
                             "status": described["status"], "note": described["note"]})
            continue
        for model in models:
            if model not in models_for(hyp):
                continue
            metric = model_metric(hyp, model)
            selected = predictions[(predictions["hypothesis_id"] == hyp["id"]) & (predictions["model"] == model)]
            eligible = page_windows[(page_windows["hypothesis_id"] == hyp["id"]) & page_windows["eligible"]
                                    & (page_windows["metric"] == metric)]
            n_control = eligible.loc[eligible["role"] == "control", "page"].nunique()
            per_arm = selected.groupby("arm")["page"].nunique().to_dict()
            row = {**base, "model": model, "metric": metric, "n_control": int(n_control),
                   "n_treated": int(sum(per_arm.values())),
                   "min_window_days": int(eligible["n_days"].min()) if len(eligible) else 0}
            if n_control < 2 or any(per_arm.get(arm, 0) < 2 for arm in arms(hyp)):
                rows.append({**row, "estimate": np.nan, "decision": DECISION_NO_DATA,
                             "decision_unadjusted": DECISION_NO_DATA, "status": "insufficient_data",
                             "note": f"treated per arm {per_arm}, control {n_control}"})
                continue
            estimate = point_effect(hyp, selected, metric)
            draws = bootstrap_draws(hyp, page_windows, model, reps, rng_for(cfg["seed"], hyp["id"], model, tag))
            alpha, alpha_adj = 1 - level, 1 - level_adj
            low, high = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
            low_adj, high_adj = np.quantile(draws, [alpha_adj / 2, 1 - alpha_adj / 2])
            rows.append({**row, "estimate": estimate, "ci_low": float(low), "ci_high": float(high),
                         "ci_low_adj": float(low_adj), "ci_high_adj": float(high_adj),
                         "decision": decide(low_adj, high_adj, hyp["threshold"]),
                         "decision_unadjusted": decide(low, high, hyp["threshold"]),
                         "status": "estimated", "note": ""})
    columns = ["run_id", "hypothesis_id", "kind", "model", "model_version", "metric", "segment", "intervention",
               "compare_to", "estimate", "ci_low", "ci_high", "ci_level", "ci_low_adj", "ci_high_adj",
               "ci_level_adj", "threshold", "decision", "decision_unadjusted", "n_treated", "n_control",
               "min_window_days", "bootstrap_reps", "status", "note"]
    return pd.DataFrame(rows).reindex(columns=columns)
