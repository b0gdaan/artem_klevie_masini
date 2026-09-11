"""Deterministic synthetic snapshot with known effects for smoke runs and tests.

The site ``primer-finance.test`` is fictional. Effects are injected so the
estimators can be checked against a known answer:

* technical pages: average position multiplied by 0.72 (28 % improvement);
* content pages: CTR multiplied by 1.30 at an unchanged position;
* local pages: local-query impressions multiplied by 1.50;
* accessibility pages: no effect (true value 0).

A site-wide position drift, demand growth, weekly and August seasonality affect
treated and control pages alike, so a naive before/after comparison is biased
while the difference-in-differences estimate is not.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .io_utils import (atomic_write_text, format_sha256sums, tree_sha256, write_csv,
                       write_json)

SEED = 20260911
START = date(2026, 2, 1)
END = date(2026, 9, 7)
BASE_URL = "https://primer-finance.test"
PAGES_PER_GROUP = 5
RAMP_DAYS = 14
GROUPS = [
    ("technical", "storitve", "Finančne storitve"),
    ("content", "nasveti", "Finančni nasveti"),
    ("local", "poslovalnice", "Poslovalnica"),
    ("accessibility", "obrazci", "Obrazec za povpraševanje"),
    ("control", "o-nas", "O podjetju"),
]
INTERVENTION_DATES = {"technical": "2026-06-22", "content": "2026-06-29",
                      "local": "2026-07-06", "accessibility": "2026-07-13"}
LINKS_DATE = "2026-07-01"
DESCRIPTIONS = {
    "technical": "Viewport, canonical, popravljene povezave, hitrejše nalaganje",
    "content": "Meta opisi, unikatni naslovi, H1, strukturirani podatki",
    "local": "Google Business Profile, lokalne ključne besede, LocalBusiness",
    "accessibility": "Alt besedila, lang, zaporedje naslovov, oznake obrazcev",
    "links": "Gradnja povratnih povezav s slovenskih spletišč",
}
TRUTH = {
    "technical": {"position_multiplier": 0.72},
    "content": {"ctr_multiplier": 1.30},
    "local": {"local_impressions_multiplier": 1.50},
    "accessibility": {},
    "control": {},
}
EXPECTED_ESTIMANDS = {"H1": 0.28, "H2": 0.30, "H3": 0.20, "H4": 0.0}
AUTHORITY = [("2026-02-01", 11), ("2026-03-01", 11), ("2026-04-01", 12), ("2026-05-01", 12),
             ("2026-06-01", 12), ("2026-07-01", 14), ("2026-08-01", 16), ("2026-09-01", 17)]


def _html(page: dict, snapshot: str, pages: list[dict]) -> str:
    group, k = page["design_group"], page["k"]
    fixed = snapshot == "after" and group != "control"
    lang = "" if group == "accessibility" and not fixed else ' lang="sl"'
    if group == "content" and not fixed:
        title = "Primer Finance"
    elif group == "control":
        title = f"{page['topic']} {k} – vse o podjetju Primer Finance in naših finančnih storitvah"
    else:
        title = f"{page['topic']} {k} | Primer Finance"
    head = [f"<title>{title}</title>"]
    if not (group == "content" and not fixed):
        head.append(f'<meta name="description" content="{page["topic"]} {k}: pregled storitev, '
                    f'pogojev in kontaktov za stranke v Sloveniji.">')
    if not (group == "technical" and not fixed):
        head.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
        head.append(f'<link rel="canonical" href="{page["url"]}">')
    if group == "local" and fixed:
        head.append('<script type="application/ld+json">{"@context": "https://schema.org", '
                    '"@type": "FinancialService", "name": "Primer Finance", "address": '
                    '{"@type": "PostalAddress", "addressLocality": "Maribor", "addressCountry": "SI"}}'
                    '</script>')
    elif group not in {"content", "local"} or fixed:
        head.append('<script type="application/ld+json">{"@context": "https://schema.org", '
                    '"@type": "Organization", "name": "Primer Finance"}</script>')

    nav = [f'<a href="{p["url"]}">{p["topic"]} {p["k"]}</a>' for p in pages
           if p["k"] == 1 or (p["design_group"] == group and p["k"] in {k - 1, k + 1})]
    body = [f"<nav>{' '.join(nav)}</nav>"]
    if group == "content" and not fixed and k <= 2:
        body.append(f"<p class=\"lead\">{page['topic']} {k}</p>")
    else:
        body.append(f"<h1>{page['topic']} {k}</h1>")
    if group == "accessibility" and not fixed:
        body += ["<h3>Podatki o stranki</h3>",
                 '<img src="/img/obrazec.png"><img src="/img/ikona.png">',
                 '<form><input type="text" name="ime"><button type="submit">Pošlji</button></form>',
                 '<a href="/kontakt/"><img src="/img/tel.svg"></a>']
    else:
        body += ["<h2>Podatki o stranki</h2>",
                 '<img src="/img/obrazec.png" alt="Primer izpolnjenega obrazca">',
                 '<form><label for="ime">Ime</label><input id="ime" type="text" name="ime">'
                 '<button type="submit">Pošlji</button></form>']
    if group == "technical" and not fixed:
        body.append('<a href="/stara-stran/">Stara stran s ceniki</a>')
    body.append("<p>Vsebina je sintetična in služi preverjanju revizijskih orodij.</p>")
    return (f"<!doctype html>\n<html{lang}>\n<head>\n<meta charset=\"utf-8\">\n"
            + "\n".join(head) + "\n</head>\n<body>\n" + "\n".join(body) + "\n</body>\n</html>\n")


def generate_snapshot(out_dir: str | Path, seed: int = SEED) -> str:
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty; raw snapshots are immutable")
    rng = np.random.default_rng(seed)
    days = pd.date_range(START, END, freq="D")
    n = len(days)
    frac = np.arange(n) / (n - 1)
    seasonal = np.where(days.dayofweek >= 5, 0.75, 1.0) * np.where(days.month == 8, 0.85, 1.0)
    demand_trend = (1 + 0.12 * frac) * seasonal
    position_drift = np.exp(-0.05 * frac)
    day_text = days.strftime("%Y-%m-%d")

    pages, interventions, gsc, lighthouse = [], [], [], []
    number = 0
    for group, slug, topic in GROUPS:
        for k in range(1, PAGES_PER_GROUP + 1):
            number += 1
            page = f"P{number:02d}"
            url = f"{BASE_URL}/{slug}/{k}/"
            base_position = rng.uniform(4.0, 20.0)
            base_demand = rng.uniform(60.0, 180.0)
            local_share = rng.uniform(0.25, 0.45)
            pages.append({"page": page, "url": url, "design_group": group, "k": k, "topic": topic})
            ramp = np.zeros(n)
            if group in INTERVENTION_DATES:
                start = pd.Timestamp(INTERVENTION_DATES[group])
                ramp = np.clip(np.asarray((days - start).days, dtype=float) / RAMP_DAYS, 0.0, 1.0)
                interventions.append({"intervention_id": f"I{number:02d}", "page": page, "type": group,
                                      "date": INTERVENTION_DATES[group],
                                      "description": DESCRIPTIONS[group]})
            truth = TRUTH[group]
            position_multiplier = 1 + (truth.get("position_multiplier", 1.0) - 1) * ramp
            position = np.maximum(1.0, base_position * position_drift * position_multiplier
                                  * np.exp(rng.normal(0, 0.06, n)))
            demand = base_demand * demand_trend * np.sqrt(10.0 / position)
            ctr_multiplier = 1 + (truth.get("ctr_multiplier", 1.0) - 1) * ramp
            for segment, share in (("general", 1 - local_share), ("local", local_share)):
                impression_multiplier = (1 + (truth.get("local_impressions_multiplier", 1.0) - 1) * ramp
                                         if segment == "local" else 1.0)
                impressions = rng.poisson(demand * share * impression_multiplier)
                segment_position = np.maximum(1.0, position * np.exp(rng.normal(0, 0.03, n)))
                ctr = np.minimum(0.9, 0.32 * segment_position ** -0.95 * ctr_multiplier)
                clicks = rng.binomial(impressions, ctr)
                gsc.append(pd.DataFrame({
                    "date": day_text, "page": page, "segment": segment, "clicks": clicks,
                    "impressions": impressions,
                    "position": np.where(impressions > 0, np.round(segment_position, 2), np.nan),
                }))
            for snapshot, when in (("before", "2026-06-01"), ("after", "2026-08-20")):
                after = snapshot == "after"
                slow = group == "technical" and not after
                lighthouse.append({
                    "page": page, "snapshot": snapshot, "date": when,
                    "performance": int(rng.uniform(45, 62) if slow else rng.uniform(80, 94) if group == "technical"
                                       else rng.uniform(62, 78)),
                    "accessibility": int(rng.uniform(62, 75) if group == "accessibility" and not after
                                         else rng.uniform(92, 100) if group == "accessibility"
                                         else rng.uniform(82, 92)),
                    "seo": int(rng.uniform(70, 82) if group == "content" and not after
                               else rng.uniform(92, 100) if group == "content" else rng.uniform(85, 95)),
                    "lcp_ms": int(rng.uniform(3600, 4500) if slow else rng.uniform(1900, 2400)
                                  if group == "technical" else rng.uniform(2400, 3000)),
                    "cls": round(float(rng.uniform(0.12, 0.25) if slow else rng.uniform(0.02, 0.08)), 3),
                    "inp_ms": int(rng.uniform(150, 350)),
                })
    interventions.append({"intervention_id": "L01", "page": "*", "type": "links", "date": LINKS_DATE,
                          "description": DESCRIPTIONS["links"]})

    out.mkdir(parents=True, exist_ok=True)
    page_frame = pd.DataFrame(pages)
    write_csv(out / "pages.csv", page_frame[["page", "url", "design_group"]])
    write_csv(out / "gsc_daily.csv", pd.concat(gsc).sort_values(["date", "page", "segment"]))
    write_csv(out / "interventions.csv", pd.DataFrame(interventions))
    write_csv(out / "lighthouse.csv", pd.DataFrame(lighthouse))
    write_csv(out / "authority.csv", pd.DataFrame(
        [{"date": d, "metric": "domain_authority", "source": "moz (sintetično)", "value": v}
         for d, v in AUTHORITY]))

    for snapshot in ("before", "after"):
        rows = []
        for page in pages:
            name = f"{page['page']}.html"
            atomic_write_text(out / "crawl" / snapshot / name, _html(page, snapshot, pages))
            rows.append({"url": page["url"], "file": name, "status": 200, "content_type": "text/html"})
        if snapshot == "before":
            rows.append({"url": f"{BASE_URL}/stara-stran/", "file": "", "status": 404,
                         "content_type": "text/html"})
        write_csv(out / "crawl" / snapshot / "index.csv", pd.DataFrame(rows).sort_values("url"))

    write_json(out / "ground_truth.json", {
        "effects": TRUTH, "intervention_dates": INTERVENTION_DATES, "links_date": LINKS_DATE,
        "ramp_days": RAMP_DAYS, "expected_estimands": EXPECTED_ESTIMANDS,
    })
    atomic_write_text(out / "SNAPSHOT.yaml", yaml.safe_dump({
        "schema_version": 1,
        "name": "smoke",
        "mode": "synthetic",
        "generator": "research.synthetic.generate_snapshot",
        "seed": seed,
        "period": {"start": START.isoformat(), "end": END.isoformat()},
        "site": f"{BASE_URL} (fiktivno spletišče)",
        "note_sl": "Sintetični podatki za preverjanje cevovoda. Niso podatki resničnega podjetja.",
        "note_ru": "Синтетические данные для проверки пайплайна. Это не данные реальной компании.",
    }, sort_keys=False, allow_unicode=True))
    tree, files = tree_sha256(out)
    atomic_write_text(out / "SHA256SUMS", format_sha256sums(files))
    return tree
