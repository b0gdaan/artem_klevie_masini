"""Tables, figures, claims registry and the public demo export of one run."""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from .artifacts import read_table, run_path  # noqa: E402
from .config import arms, inferential  # noqa: E402
from .data import available_until, load_tables  # noqa: E402
from .estimate import expected_ctr, metric_frame  # noqa: E402
from .io_utils import atomic_write_text, read_json, write_csv, write_json  # noqa: E402

INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE, ORANGE, AQUA, BLUE_LIGHT, NEUTRAL = "#2a78d6", "#eb6834", "#1baf7a", "#86b6ef", "#f0efec"
PUBLIC_NAME = "demo_public"
PRINT_NAME = "thesis_print"
INTERVENTION_SL = {"technical": "tehnična", "content": "vsebinska", "local": "lokalna",
                   "accessibility": "dostopnost", "links": "povratne povezave"}
METRIC_SL = {"position": "povprečni položaj", "ctr_adjusted": "CTR, prilagojen položaju", "clicks": "kliki",
             "domain_authority": "Domain Authority", "ctr_raw": "neprilagojen CTR"}
MODEL_SL = {"did": "razlika razlik (glavni model)", "naive_prepost": "pred/po brez kontrolne skupine",
            "did_raw_ctr": "razlika razlik brez prilagoditve položaju", "descriptive": "opisno"}
MODE_SL = {"synthetic": "Sintetični scenarij: fiktivno spletišče z znanimi vnesenimi učinki",
           "snapshot": "Shranjen posnetek podatkov resničnega spletišča"}
SECTION = {"H1": "3.3", "H2": "3.3", "H3": "3.3", "H4": "3.4", "H5": "3.3"}


def _clean(value):
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return None if math.isnan(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _records(frame: pd.DataFrame) -> list[dict]:
    return [_clean(row) for row in frame.to_dict(orient="records")]


def _pct(value) -> str:
    return "—" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value * 100:+.1f} %"


def _md_table(frame: pd.DataFrame, headers: dict[str, str]) -> str:
    lines = ["| " + " | ".join(headers.values()) + " |", "|" + "---|" * len(headers)]
    for row in frame.to_dict(orient="records"):
        lines.append("| " + " | ".join(str(row[c]) for c in headers) + " |")
    return "\n".join(lines) + "\n"


def event_series(cfg, hyp, page_windows, panel_page, panel_segment, curve) -> dict:
    design = cfg["design"]
    avail = available_until(cfg)
    week_lo = math.floor(-(design["buffer_days"] + design["pre_days"]) / 7)
    base_hi = math.floor((-design["buffer_days"] - 1) / 7)
    week_end = math.ceil((design["ramp_days"] + design["post_days"]) / 7)
    metric = hyp["metric"]
    frame = metric_frame(panel_page, panel_segment, hyp.get("segment", "all"))
    frame = frame[frame["date"] <= avail].assign(
        expected=lambda f: np.where(f["impressions"] > 0,
                                    f["impressions"] * expected_ctr(curve, f["position"].fillna(1.0)), 0.0))
    frame = frame.assign(timestamp=pd.to_datetime(frame["date"]))
    by_page = {page: group for page, group in frame.groupby("page")}
    names = {arm: f"Obravnavane strani – {INTERVENTION_SL[kind]}" for arm, kind in arms(hyp).items()}
    eligible = page_windows[(page_windows["hypothesis_id"] == hyp["id"]) & (page_windows["metric"] == metric)
                            & page_windows["eligible"]][["arm", "window_key", "page", "role"]].drop_duplicates()
    pieces = []
    for arm, key, page, role in eligible.itertuples(index=False):
        if role == "control" and arm != "a":
            continue
        rows = by_page[page]
        week = np.floor((rows["timestamp"] - pd.Timestamp(key)).dt.days / 7).astype(int)
        rows = rows.assign(week=week)
        rows = rows[(rows["week"] >= week_lo) & (rows["week"] < week_end)]
        shown = rows[rows["impressions"] > 0]
        if metric == "position":
            weekly = shown.groupby("week")["position"].mean()
        elif metric == "clicks":
            weekly = rows.groupby("week")["clicks"].mean()
        else:
            grouped = shown.groupby("week")
            weekly = grouped["clicks"].sum() / grouped["expected"].sum()
        baseline = weekly[(weekly.index >= week_lo) & (weekly.index <= base_hi)].mean()
        if not baseline or math.isnan(baseline):
            continue
        name = names[arm] if role == "treated" else "Kontrolne strani"
        pieces.append(pd.DataFrame({"name": name, "role": role, "week": weekly.index,
                                    "index": 100 * weekly.to_numpy() / baseline}))
    weeks = list(range(week_lo, week_end))
    series = []
    if pieces:
        combined = pd.concat(pieces).groupby(["name", "role", "week"], as_index=False)["index"].mean()
        order = [names[a] for a in sorted(names)] + ["Kontrolne strani"]
        for name in order:
            part = combined[combined["name"] == name].set_index("week")["index"]
            if part.empty:
                continue
            role = "control" if name == "Kontrolne strani" else "treated"
            series.append({"name": name, "role": role,
                           "values": [round(float(part[w]), 3) if w in part.index else None for w in weeks]})
    return {"hypothesis_id": hyp["id"], "metric": metric, "metric_label": METRIC_SL[metric],
            "lower_is_better": metric == "position", "weeks": weeks,
            "ramp_weeks": math.ceil(design["ramp_days"] / 7), "series": series}


def _style(ax, grid_axis="y"):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.png")
    fig.savefig(tmp, dpi=150, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    tmp.replace(path)
    return path


def figure_effects(metrics: pd.DataFrame, path: Path) -> Path:
    rows = metrics[(metrics["kind"] != "descriptive") & (metrics["status"] == "estimated")]
    fig, ax = plt.subplots(figsize=(9, 0.8 * max(len(rows), 1) + 1.6))
    _style(ax, grid_axis="x")
    y_positions = np.arange(len(rows))[::-1]
    for y, row in zip(y_positions, rows.itertuples()):
        ax.plot([row.ci_low * 100, row.ci_high * 100], [y, y], color=BLUE_LIGHT, linewidth=6,
                solid_capstyle="round")
        ax.plot([row.ci_low_adj * 100, row.ci_high_adj * 100], [y, y], color=BLUE, linewidth=1.5)
        ax.plot([row.estimate * 100], [y], "o", color=BLUE, markersize=7, markeredgecolor=SURFACE,
                markeredgewidth=2)
        ax.plot([row.threshold * 100], [y], marker="|", color=INK_2, markersize=16, markeredgewidth=2)
        ax.annotate(f"{row.estimate * 100:+.1f} % · {row.decision}", xy=(1.02, y), xycoords=("axes fraction", "data"),
                    va="center", fontsize=9, color=INK)
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.set_yticks(y_positions, [f"{r.hypothesis_id}: {METRIC_SL[r.metric]}" for r in rows.itertuples()])
    ax.set_xlabel("Ocenjeni relativni učinek (%)", color=INK_2, fontsize=9)
    level, level_adj = rows["ci_level"].iloc[0], rows["ci_level_adj"].iloc[0]
    ax.legend(handles=[Line2D([], [], color=BLUE_LIGHT, linewidth=6, label=f"{level:.0%} IZ"),
                       Line2D([], [], color=BLUE, linewidth=1.5, label=f"Bonferroni {level_adj:.2%} IZ"),
                       Line2D([], [], color=INK_2, marker="|", linestyle="", markersize=12, label="prag hipoteze")],
              loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, fontsize=9)
    fig.subplots_adjust(left=0.24, right=0.66, top=0.82, bottom=0.18)
    return _save(fig, path)


def figure_series(series: list[dict], path: Path) -> Path:
    n = max(len(series), 1)
    cols = 2
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(10, 3.3 * rows), squeeze=False)
    for ax, item in zip(axes.flat, series):
        _style(ax)
        ax.axvspan(0, item["ramp_weeks"], color=NEUTRAL, linewidth=0)
        ax.axvline(0, color=INK_2, linewidth=1)
        ax.axhline(100, color=AXIS, linewidth=0.8)
        colors = iter([BLUE, AQUA])
        for line in item["series"]:
            color = MUTED if line["role"] == "control" else next(colors)
            values = [np.nan if v is None else v for v in line["values"]]
            ax.plot(item["weeks"], values, color=color, linewidth=2, label=line["name"])
        suffix = " (nižje = bolje)" if item["lower_is_better"] else ""
        ax.set_title(f"{item['hypothesis_id']}: {item['metric_label']}{suffix}", fontsize=10, color=INK, loc="left")
        ax.legend(frameon=False, fontsize=8)
    for ax in list(axes.flat)[len(series):]:
        ax.set_visible(False)
    fig.supxlabel("Tedni glede na uvedbo ukrepa (osenčeno: uvajanje, izključeno iz ocene)", fontsize=9, color=INK_2)
    fig.supylabel("Indeks (predobdobje = 100)", fontsize=9, color=INK_2)
    fig.tight_layout()
    return _save(fig, path)


def figure_audit(summary: pd.DataFrame, path: Path) -> Path:
    totals = summary.groupby("category")[["before", "after"]].sum().reindex(
        ["technical", "content", "accessibility"]).fillna(0)
    labels = {"technical": "Tehnične", "content": "Vsebinske", "accessibility": "Dostopnost"}
    fig, ax = plt.subplots(figsize=(8, 3.2))
    _style(ax, grid_axis="x")
    y = np.arange(len(totals))[::-1]
    for offset, column, color, name in ((0.2, "before", ORANGE, "Pred optimizacijo"),
                                        (-0.2, "after", BLUE, "Po optimizaciji")):
        values = totals[column].to_numpy()
        ax.barh(y + offset, values, height=0.36, color=color, label=name)
        for yi, value in zip(y, values):
            ax.annotate(f"{int(value)}", xy=(value, yi + offset), xytext=(4, 0), textcoords="offset points",
                        va="center", fontsize=9, color=INK)
    ax.set_yticks(y, [labels[c] for c in totals.index])
    ax.set_xlabel("Število najdenih težav", color=INK_2, fontsize=9)
    ax.legend(frameon=False, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    fig.subplots_adjust(left=0.14, right=0.96, top=0.84, bottom=0.18)
    return _save(fig, path)


def build_report(ctx) -> list[Path]:
    cfg, run_dir = ctx.config, ctx.run_dir
    out = run_path(run_dir, "report")
    metrics = read_table(run_path(run_dir, "metrics"))
    ablation = read_table(run_path(run_dir, "ablation"))
    placebo = read_table(run_path(run_dir, "placebo"))
    page_windows = read_table(run_path(run_dir, "page_windows"))
    curve = read_json(run_path(run_dir, "curve"))
    panel_page = read_table(ctx.processed_dir / "panel_page_day.csv")
    panel_segment = read_table(ctx.processed_dir / "panel_segment_day.csv")
    tables = load_tables(ctx.snapshot_dir)
    statements = {h["id"]: h.get("statement_sl", "") for h in cfg["hypotheses"]}
    limitations = {h["id"]: h.get("limitation_sl", "") for h in cfg["hypotheses"]}
    outputs = []

    before = read_table(ctx.processed_dir / "audit_issues_before.csv")
    after = read_table(ctx.processed_dir / "audit_issues_after.csv")
    counts = [frame.groupby(["category", "issue"]).size().rename(label)
              for frame, label in ((before, "before"), (after, "after"))]
    audit = pd.concat(counts, axis=1).fillna(0).astype(int).reset_index().sort_values(["category", "issue"])
    outputs.append(write_csv(out / "tables" / "audit_summary.csv", audit))

    lighthouse = tables["lighthouse.csv"].merge(tables["pages.csv"][["page", "design_group"]], on="page")
    lighthouse_summary = (lighthouse.groupby(["design_group", "snapshot"])
                          [["performance", "accessibility", "seo", "lcp_ms", "cls", "inp_ms"]]
                          .median().reset_index().sort_values(["design_group", "snapshot"], ascending=[True, False]))
    outputs.append(write_csv(out / "tables" / "lighthouse_summary.csv", lighthouse_summary))

    hypotheses = metrics.assign(statement=metrics["hypothesis_id"].map(statements))
    outputs.append(write_csv(out / "tables" / "hypotheses.csv", hypotheses))

    series = [event_series(cfg, h, page_windows, panel_page, panel_segment, curve) for h in inferential(cfg)]
    figures = out / "figures"
    outputs += [figure_effects(metrics, figures / "effects.png"), figure_series(series, figures / "timeseries.png"),
                figure_audit(audit, figures / "audit_issues.png")]

    claims = []
    for row in metrics.itertuples():
        if row.status == "estimated":
            text = (f"{row.hypothesis_id}: ocenjeni učinek {_pct(row.estimate)} "
                    f"(Bonferroni {row.ci_level_adj:.2%} IZ {_pct(row.ci_low_adj)} do {_pct(row.ci_high_adj)}); "
                    f"odločitev: {row.decision}.")
            interval = f"[{row.ci_low_adj:.6f}; {row.ci_high_adj:.6f}]"
        else:
            text = f"{row.hypothesis_id}: {row.decision} ({row.note})."
            interval = ""
        limitation = "; ".join(x for x in (limitations[row.hypothesis_id],
                                           "sintetični podatki, ni dokaz za resnično spletišče"
                                           if cfg["mode"] == "synthetic" else "") if x)
        claims.append({"claim_id": f"C-{row.hypothesis_id}", "section": SECTION.get(row.hypothesis_id, "3"),
                       "statement": text, "run_id": ctx.run_id, "file": "metrics/metrics.csv",
                       "filter": f"hypothesis_id == '{row.hypothesis_id}' and model == '{row.model}'",
                       "metric": "estimate", "value": row.estimate, "interval": interval,
                       "limitation": limitation})
    claims.append({"claim_id": "C-AUDIT", "section": "3.2",
                   "statement": f"Revizija je našla {int(audit['before'].sum())} težav pred in "
                                f"{int(audit['after'].sum())} po optimizaciji.",
                   "run_id": ctx.run_id, "file": "report/tables/audit_summary.csv", "filter": "all rows",
                   "metric": "sum(before)", "value": float(audit["before"].sum()), "interval": "",
                   "limitation": "hevristični pregled HTML; ne nadomešča Lighthouse/WAVE"})
    outputs.append(write_csv(out / "claims.csv", pd.DataFrame(claims)))

    dates = panel_page["date"]
    truth_path = ctx.snapshot_dir / "ground_truth.json"
    manifest = ctx.manifest
    site = {
        "schema_version": 1, "public_name": PUBLIC_NAME, "mode": cfg["mode"], "mode_label": MODE_SL[cfg["mode"]],
        "run_id": ctx.run_id, "code_commit": manifest["code_commit"],
        "working_tree_dirty": manifest["working_tree_dirty"], "model_version": metrics["model_version"].iloc[0],
        "data_period": {"start": dates.min(), "end": dates.max()},
        "analysis_cutoff": cfg["data"]["analysis_cutoff"], "available_until": available_until(cfg),
        "run_created_at_utc": manifest["created_at_utc"], "data_sha256": manifest["data_sha256"],
        "config_sha256": manifest["config_sha256"], "bootstrap_reps": cfg["inference"]["bootstrap_reps"],
        "hypotheses": _records(hypotheses), "series": series,
        "ablation": _records(ablation.assign(model_label=ablation["model"].map(MODEL_SL))),
        "placebo": _records(placebo), "audit": _records(audit), "lighthouse": _records(lighthouse_summary),
        "authority": _records(tables["authority.csv"]), "ctr_curve": curve,
        "truth": read_json(truth_path)["expected_estimands"] if cfg["mode"] == "synthetic" and truth_path.is_file() else None,
    }
    outputs.append(write_json(out / "site_data.json", _clean(site)))

    table = hypotheses.assign(
        ocena=hypotheses.apply(lambda r: f"{r['estimate']:+.0f} točk" if r["kind"] == "descriptive"
                               else _pct(r["estimate"]), axis=1),
        iz=hypotheses.apply(lambda r: "—" if r["status"] != "estimated"
                            else f"{_pct(r['ci_low_adj'])} … {_pct(r['ci_high_adj'])}", axis=1),
        prag=hypotheses.apply(lambda r: f"{r['threshold']:g} točk" if r["kind"] == "descriptive"
                              else _pct(r["threshold"]), axis=1))
    ablation_table = ablation.assign(model_label=ablation["model"].map(MODEL_SL), ocena=ablation["estimate"].map(_pct),
                                     iz=ablation.apply(lambda r: f"{_pct(r['ci_low'])} … {_pct(r['ci_high'])}", axis=1))
    placebo_table = placebo.assign(ocena=placebo["estimate"].map(_pct),
                                   iz=placebo.apply(lambda r: f"{_pct(r['ci_low'])} … {_pct(r['ci_high'])}", axis=1),
                                   nic=placebo["contains_zero"].map({True: "da", False: "ne"}))
    text = [f"# Poročilo zagona `{ctx.run_id}`\n",
            f"Način: **{MODE_SL[cfg['mode']]}**. Obdobje podatkov {dates.min()} – {dates.max()}, "
            f"presečni datum {cfg['data']['analysis_cutoff']} (končni podatki do {available_until(cfg)}). "
            f"Koda `{manifest['code_commit'][:12]}`, model `{site['model_version']}`.\n",
            "## Hipoteze\n",
            _md_table(table, {"hypothesis_id": "ID", "statement": "Trditev", "ocena": "Ocena",
                              "iz": "Bonferroni IZ", "prag": "Prag", "decision": "Odločitev"}),
            "## Ablacija in robustnost\n",
            _md_table(ablation_table, {"hypothesis_id": "ID", "model_label": "Model", "ocena": "Ocena",
                                       "iz": "95 % IZ", "n_treated": "Obravnavane", "n_control": "Kontrolne"}),
            "\n## Placebo test (lažni datum uvedbe)\n",
            _md_table(placebo_table, {"hypothesis_id": "ID", "ocena": "Ocena", "iz": "95 % IZ",
                                      "nic": "IZ vsebuje 0"}),
            "\n## Revizija spletišča\n",
            _md_table(audit, {"category": "Kategorija", "issue": "Težava", "before": "Pred", "after": "Po"})]
    outputs.append(atomic_write_text(out / "report.md", "\n".join(text)))
    return outputs
