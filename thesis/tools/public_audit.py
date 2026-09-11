"""Capture a single public page and audit it without inventing traffic data."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from research.audit import audit_site
from research.crawl import HttpFetcher


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Use a new snapshot directory; existing evidence is immutable")
    fetched = HttpFetcher().fetch(args.url)
    if fetched.status != 200 or "html" not in fetched.content_type:
        raise RuntimeError(f"No usable HTML: {fetched.status} {fetched.content_type}")
    facts, issues = audit_site([{"url": args.url, "status": fetched.status,
                                "html": fetched.body.decode("utf-8", errors="replace")}])
    args.out.mkdir(parents=True)
    (args.out / "page.html").write_bytes(fetched.body)
    facts.to_csv(args.out / "facts.csv", index=False)
    issues.to_csv(args.out / "issues.csv", index=False)
    evidence = {"mode": "public_html_observation", "requested_url": args.url,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "http_status": fetched.status, "content_type": fetched.content_type,
                "sha256": hashlib.sha256(fetched.body).hexdigest(),
                "scope": "One HTML response; no JavaScript rendering, traffic, rankings or causal effect measured",
                "issue_count": len(issues)}
    (args.out / "provenance.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
