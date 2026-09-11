"""On-page SEO and accessibility checks for crawled HTML.

The checks are deterministic heuristics. They do not replace Lighthouse, WAVE or
axe: accessibility findings here cover a documented subset of WCAG success
criteria (1.1.1 alt text, 1.3.1 headings/labels, 2.4.4 link purpose, 3.1.1 lang).
Length limits for titles and descriptions are conventions from SEO tools, not
rules published by Google.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
from bs4 import BeautifulSoup

TITLE_MIN = 10
TITLE_MAX = 60
META_DESCRIPTION_MAX = 160

ISSUE_CATEGORY = {
    "http_error": "technical",
    "missing_viewport": "technical",
    "missing_canonical": "technical",
    "noindex": "technical",
    "broken_internal_link": "technical",
    "missing_title": "content",
    "title_too_short": "content",
    "title_too_long": "content",
    "duplicate_title": "content",
    "missing_meta_description": "content",
    "meta_description_too_long": "content",
    "duplicate_meta_description": "content",
    "missing_h1": "content",
    "multiple_h1": "content",
    "missing_structured_data": "content",
    "invalid_structured_data": "content",
    "img_missing_alt": "accessibility",
    "missing_lang": "accessibility",
    "heading_level_skip": "accessibility",
    "input_missing_label": "accessibility",
    "empty_link_text": "accessibility",
}
_HEADING = re.compile(r"^h[1-6]$")
_UNLABELLED_TYPES = {"hidden", "submit", "button", "image", "reset"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _structured_data(soup: BeautifulSoup) -> tuple[list[str], int]:
    types, invalid = [], 0
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "")
        except json.JSONDecodeError:
            invalid += 1
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            kind = item.get("@type") if isinstance(item, dict) else None
            types.extend(kind if isinstance(kind, list) else [kind] if kind else [])
    return sorted(types), invalid


def _link_text(anchor) -> str:
    text = anchor.get_text(strip=True) or anchor.get("aria-label", "").strip()
    if not text:
        text = " ".join(img.get("alt", "").strip() for img in anchor.find_all("img")).strip()
    return text


def _labelled(control, soup: BeautifulSoup) -> bool:
    if control.get("aria-label") or control.get("aria-labelledby") or control.find_parent("label"):
        return True
    control_id = control.get("id")
    return bool(control_id and soup.find("label", attrs={"for": control_id}))


def audit_html(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    host = urlsplit(url).netloc.lower()
    title = soup.title.get_text(strip=True) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    description = (description_tag.get("content") or "").strip() if description_tag else ""
    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    headings = [int(tag.name[1]) for tag in soup.find_all(_HEADING)]
    html_tag = soup.find("html")
    types, invalid = _structured_data(soup)

    internal, empty_links = set(), 0
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not _link_text(anchor):
            empty_links += 1
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        target = normalize_url(urljoin(url, href))
        if urlsplit(target).netloc == host:
            internal.add(target)

    controls = [c for c in soup.find_all(["input", "select", "textarea"])
                if (c.get("type") or "").lower() not in _UNLABELLED_TYPES]
    images = soup.find_all("img")
    return {
        "url": normalize_url(url),
        "title": title,
        "title_length": len(title),
        "meta_description": description,
        "meta_description_length": len(description),
        "h1_count": len(soup.find_all("h1")),
        "heading_level_skips": sum(1 for a, b in zip(headings, headings[1:]) if b > a + 1),
        "has_canonical": soup.find("link", rel="canonical") is not None,
        "has_viewport": soup.find("meta", attrs={"name": "viewport"}) is not None,
        "noindex": bool(robots and "noindex" in (robots.get("content") or "").lower()),
        "lang": (html_tag.get("lang") or "").strip() if html_tag else "",
        "img_count": len(images),
        "img_missing_alt": sum(1 for img in images if img.get("alt") is None),
        "structured_data_types": "|".join(types),
        "invalid_structured_data": invalid,
        "internal_links": sorted(internal),
        "empty_link_text": empty_links,
        "inputs_without_label": sum(1 for c in controls if not _labelled(c, soup)),
    }


def audit_site(records: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Audit crawl records ``{url, status, html}``; return (page facts, issues)."""
    status_of = {normalize_url(r["url"]): int(r["status"]) for r in records}
    facts, issues = [], []

    def add(url, issue, detail=""):
        issues.append({"url": url, "issue": issue, "category": ISSUE_CATEGORY[issue], "detail": detail})

    for record in sorted(records, key=lambda r: normalize_url(r["url"])):
        url = normalize_url(record["url"])
        if int(record["status"]) >= 400:
            add(url, "http_error", str(record["status"]))
            continue
        if not record.get("html"):
            continue
        page = audit_html(record["html"], url)
        facts.append(page)
        if not page["title"]:
            add(url, "missing_title")
        elif page["title_length"] < TITLE_MIN:
            add(url, "title_too_short", str(page["title_length"]))
        elif page["title_length"] > TITLE_MAX:
            add(url, "title_too_long", str(page["title_length"]))
        if not page["meta_description"]:
            add(url, "missing_meta_description")
        elif page["meta_description_length"] > META_DESCRIPTION_MAX:
            add(url, "meta_description_too_long", str(page["meta_description_length"]))
        if page["h1_count"] == 0:
            add(url, "missing_h1")
        elif page["h1_count"] > 1:
            add(url, "multiple_h1", str(page["h1_count"]))
        if not page["has_canonical"]:
            add(url, "missing_canonical")
        if not page["has_viewport"]:
            add(url, "missing_viewport")
        if page["noindex"]:
            add(url, "noindex")
        if not page["lang"]:
            add(url, "missing_lang")
        if page["img_missing_alt"]:
            add(url, "img_missing_alt", str(page["img_missing_alt"]))
        if page["heading_level_skips"]:
            add(url, "heading_level_skip", str(page["heading_level_skips"]))
        if page["inputs_without_label"]:
            add(url, "input_missing_label", str(page["inputs_without_label"]))
        if page["empty_link_text"]:
            add(url, "empty_link_text", str(page["empty_link_text"]))
        if page["invalid_structured_data"]:
            add(url, "invalid_structured_data", str(page["invalid_structured_data"]))
        elif not page["structured_data_types"]:
            add(url, "missing_structured_data")
        for target in page["internal_links"]:
            if status_of.get(target, 200) >= 400:
                add(url, "broken_internal_link", target)

    for field, issue in (("title", "duplicate_title"), ("meta_description", "duplicate_meta_description")):
        counts: dict[str, list[str]] = {}
        for page in facts:
            if page[field] and not page["noindex"]:
                counts.setdefault(page[field], []).append(page["url"])
        for value, urls in counts.items():
            if len(urls) > 1:
                for url in urls:
                    add(url, issue, f"shared by {len(urls)} pages")

    fact_frame = pd.DataFrame(facts)
    if not fact_frame.empty:
        fact_frame["internal_links"] = fact_frame["internal_links"].map(len)
    issue_frame = pd.DataFrame(issues, columns=["url", "issue", "category", "detail"])
    issue_frame = issue_frame.sort_values(["url", "issue", "detail"]).reset_index(drop=True)
    return fact_frame, issue_frame
