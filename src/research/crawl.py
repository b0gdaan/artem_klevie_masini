"""Polite same-host crawler that writes an immutable raw crawl snapshot.

``HttpFetcher`` is the only component that touches the network. It honours
robots.txt and waits between requests. ``DirectoryFetcher`` serves a local
folder so tests and demonstrations run offline.
"""
from __future__ import annotations

import csv
import io
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

from .audit import normalize_url
from .io_utils import atomic_write_bytes, atomic_write_text

USER_AGENT = "research-seo-audit/0.1 (diploma thesis; contact via site owner)"


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    body: bytes


class DirectoryFetcher:
    def __init__(self, root: str | Path, base_url: str):
        self.root = Path(root)
        self.base_url = normalize_url(base_url)

    def fetch(self, url: str) -> FetchResult:
        path = urlsplit(url).path.lstrip("/")
        candidates = [self.root / path / "index.html"] if path.endswith("/") or not path else [
            self.root / f"{path}.html", self.root / path / "index.html", self.root / path]
        for candidate in candidates:
            if candidate.is_file():
                return FetchResult(url, 200, "text/html", candidate.read_bytes())
        return FetchResult(url, 404, "text/html", b"")


class HttpFetcher:
    def __init__(self, delay_seconds: float = 1.0, timeout: float = 20.0):
        import requests

        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delay = delay_seconds
        self.timeout = timeout
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._last = 0.0

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = robotparser.RobotFileParser(origin + "/robots.txt")
            try:
                parser.read()
            except OSError:
                parser = None
            self._robots[origin] = parser
        parser = self._robots[origin]
        return True if parser is None else parser.can_fetch(USER_AGENT, url)

    def fetch(self, url: str) -> FetchResult:
        if not self.allowed(url):
            return FetchResult(url, 999, "robots-disallowed", b"")
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        self._last = time.monotonic()
        return FetchResult(url, response.status_code,
                           response.headers.get("Content-Type", ""), response.content)


def crawl(start_url: str, fetcher, max_pages: int = 200) -> list[dict]:
    from bs4 import BeautifulSoup

    start = normalize_url(start_url)
    host = urlsplit(start).netloc
    queue, seen, records = deque([start]), {start}, []
    while queue and len(records) < max_pages:
        url = queue.popleft()
        result = fetcher.fetch(url)
        html = result.body.decode("utf-8", errors="replace") if "html" in result.content_type else ""
        records.append({"url": url, "status": result.status, "content_type": result.content_type,
                        "html": html})
        if result.status >= 400 or not html:
            continue
        for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            href = anchor["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            target = normalize_url(urljoin(url, href))
            if urlsplit(target).netloc == host and target not in seen:
                seen.add(target)
                queue.append(target)
    return records


def write_crawl(records: list[dict], out_dir: str | Path) -> Path:
    """Write ``index.csv`` plus one HTML file per page; refuse to overwrite a snapshot."""
    out_dir = Path(out_dir)
    if (out_dir / "index.csv").exists():
        raise FileExistsError(f"{out_dir} already holds a crawl; raw snapshots are immutable")
    rows = []
    for number, record in enumerate(sorted(records, key=lambda r: r["url"]), start=1):
        name = f"page_{number:04d}.html" if record.get("html") else ""
        if name:
            atomic_write_bytes(out_dir / name, record["html"].encode("utf-8"))
        rows.append({"url": record["url"], "file": name, "status": record["status"],
                     "content_type": record.get("content_type", "")})
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["url", "file", "status", "content_type"],
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return atomic_write_text(out_dir / "index.csv", buffer.getvalue())


def load_crawl(crawl_dir: str | Path) -> list[dict]:
    crawl_dir = Path(crawl_dir)
    with (crawl_dir / "index.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    records = []
    for row in rows:
        html = (crawl_dir / row["file"]).read_text(encoding="utf-8") if row["file"] else ""
        records.append({"url": row["url"], "status": int(row["status"]), "html": html})
    return records
