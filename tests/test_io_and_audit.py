import pytest

from research.audit import audit_html, audit_site, normalize_url
from research.crawl import DirectoryFetcher, crawl, load_crawl, write_crawl
from research.io_utils import atomic_write_text, sha256_bytes, tree_sha256

PAGE_A = """<!doctype html><html><head><title>Kratko</title>
<script type="application/ld+json">{bad json</script></head>
<body><h1>Ena</h1><h1>Dve</h1><h4>Preskok</h4>
<img src="a.png"><img src="b.png" alt=""><img src="c.png">
<a href="/b/">B</a><a href="/missing/"></a><a href="https://other.test/x">zunaj</a>
<form><input id="q" type="text"><label>Ime <input type="text"></label><input type="hidden" name="t"></form>
</body></html>"""
PAGE_B = """<!doctype html><html lang="sl"><head><title>Kratko</title>
<meta name="description" content="Opis"><meta name="viewport" content="width=device-width">
<link rel="canonical" href="https://example.test/b/">
<script type="application/ld+json">{"@type": ["Organization", "LocalBusiness"]}</script></head>
<body><h1>B</h1><h2>Pod</h2><a href="/a/#top">A</a></body></html>"""


def test_sha256_known_value():
    assert sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_atomic_write_keeps_previous_file_when_validation_fails(tmp_path):
    target = tmp_path / "result.txt"
    atomic_write_text(target, "old")

    def reject(path):
        raise ValueError("incomplete output")

    with pytest.raises(ValueError):
        atomic_write_text(target, "new", validate=reject)
    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [target]


def test_tree_hash_detects_same_size_change(tmp_path):
    (tmp_path / "x.csv").write_bytes(b"a,1\n")
    before = tree_sha256(tmp_path)[0]
    (tmp_path / "x.csv").write_bytes(b"a,2\n")
    assert tree_sha256(tmp_path)[0] != before


def test_tree_hash_is_independent_of_platform_path_ordering(tmp_path):
    for name in ("b.txt", "SHA256SUMS", "A.txt", "crawl/x.html", "Z/y.csv"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(name.encode())
    tree, files = tree_sha256(tmp_path)
    assert list(files) == ["A.txt", "Z/y.csv", "b.txt", "crawl/x.html"]
    expected = "".join(f"{sha256_bytes(n.encode())}  {n}\n" for n in files)
    assert tree == sha256_bytes(expected.encode())


def test_normalize_url_drops_fragment_and_lowercases_host():
    assert normalize_url("HTTPS://Example.TEST/a/#top") == "https://example.test/a/"
    assert normalize_url("https://example.test") == "https://example.test/"


def test_audit_html_hand_counted_example():
    facts = audit_html(PAGE_A, "https://example.test/a/")
    assert facts["title_length"] == 6
    assert facts["h1_count"] == 2
    assert facts["heading_level_skips"] == 1
    assert facts["img_count"] == 3 and facts["img_missing_alt"] == 2
    assert facts["invalid_structured_data"] == 1
    assert facts["empty_link_text"] == 1
    assert facts["inputs_without_label"] == 1
    assert facts["internal_links"] == ["https://example.test/b/", "https://example.test/missing/"]
    assert not facts["has_canonical"] and not facts["has_viewport"] and facts["lang"] == ""
    other = audit_html(PAGE_B, "https://example.test/b/")
    assert other["structured_data_types"] == "LocalBusiness|Organization"
    assert other["internal_links"] == ["https://example.test/a/"]


def test_audit_site_issues_hand_counted_example():
    records = [{"url": "https://example.test/a/", "status": 200, "html": PAGE_A},
               {"url": "https://example.test/b/", "status": 200, "html": PAGE_B},
               {"url": "https://example.test/missing/", "status": 404, "html": ""}]
    _, issues = audit_site(records)
    found = {(row.url.rsplit("/", 2)[-2], row.issue) for row in issues.itertuples()}
    assert found == {
        ("a", "title_too_short"), ("a", "missing_meta_description"), ("a", "multiple_h1"),
        ("a", "missing_canonical"), ("a", "missing_viewport"), ("a", "missing_lang"), ("a", "img_missing_alt"),
        ("a", "heading_level_skip"), ("a", "input_missing_label"), ("a", "empty_link_text"),
        ("a", "invalid_structured_data"), ("a", "broken_internal_link"), ("a", "duplicate_title"),
        ("b", "title_too_short"), ("b", "duplicate_title"), ("missing", "http_error"),
    }


def test_offline_crawl_roundtrip(tmp_path, no_network):
    site = tmp_path / "site"
    (site / "a").mkdir(parents=True)
    (site / "index.html").write_text('<a href="/a/">A</a><a href="/missing/">X</a>', encoding="utf-8")
    (site / "a" / "index.html").write_text('<a href="/">Domov</a>', encoding="utf-8")
    records = crawl("https://example.test/", DirectoryFetcher(site, "https://example.test/"))
    assert {(r["url"], r["status"]) for r in records} == {
        ("https://example.test/", 200), ("https://example.test/a/", 200), ("https://example.test/missing/", 404)}
    write_crawl(records, tmp_path / "snapshot")
    assert {(r["url"], r["status"]) for r in load_crawl(tmp_path / "snapshot")} == \
        {(r["url"], r["status"]) for r in records}
    with pytest.raises(FileExistsError):
        write_crawl(records, tmp_path / "snapshot")
