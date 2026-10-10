from __future__ import annotations

import json

from conftest import gig_props, page_html

from fiverr_scraper import (
    Gig,
    flatten,
    packages_to_csv,
    parse_gig_page,
    to_json,
    to_jsonl,
    write_csv,
)


def details():
    return parse_gig_page(page_html(gig_props()), "https://www.fiverr.com/x/y")


def test_flatten_prefixes_the_seller_and_serializes_nested_lists():
    row = flatten(details())
    assert row["seller_username"] == "pixelcraft_studio"
    assert row["seller_level"] == "level_two_seller"
    assert row["tags"] == "logo | brand identity"
    assert json.loads(row["packages"])[0]["tier"] == "basic"
    assert row["pro"] == "false"


def test_write_csv_uses_a_bom_for_excel(tmp_path):
    path = tmp_path / "gigs.csv"
    count = write_csv([Gig(gig_id=1, title="logo é", url="u")], path)
    assert count == 1
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "logo é" in raw.decode("utf-8-sig")


def test_packages_csv(tmp_path):
    path = tmp_path / "packages.csv"
    text = packages_to_csv([details()], path)
    assert text.splitlines()[0].startswith("gig_id,title,seller_username")
    assert len(text.strip().splitlines()) == 4
    assert path.read_text(encoding="utf-8-sig") == text


def test_json_and_jsonl():
    gig = Gig(gig_id=1, title="t", url="u")
    assert json.loads(to_json([gig]))[0]["gig_id"] == 1
    assert to_jsonl([gig, gig]).count("\n") == 2
