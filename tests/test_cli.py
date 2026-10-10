from __future__ import annotations

import csv
import io
import json

import pytest
from conftest import FakeClient, card, gig_props, listing_props, page_html, seller_props

from fiverr_scraper import FiverrScraper, Gig
from fiverr_scraper.cli import build_parser, main, order_gigs

BASE = "https://www.fiverr.com/search/gigs?query=logo%20design"
GIG = "https://www.fiverr.com/pixelcraft_studio/design-a-logo-777"


def scraper_for(responses):
    return FiverrScraper(client=FakeClient(responses), transient_errors=(), sleep=lambda s: None)


def test_parser_search_options():
    args = build_parser().parse_args(
        [
            "search",
            "logo design",
            "brand identity",
            "--sort",
            "best_selling",
            "--seller-level",
            "top_rated",
            "level_2",
            "--seller-country",
            "US",
            "GB",
            "--delivery-days",
            "3",
            "--min-price",
            "20",
            "--pro",
            "--facet",
            "style=retro",
            "--facet",
            "service_offerings=subscription",
            "--order",
            "price-desc",
            "-p",
            "2",
            "-f",
            "csv",
        ]
    )
    assert args.queries == ["logo design", "brand identity"]
    assert args.sort == "best_selling"
    assert args.seller_level == ["top_rated", "level_2"]
    assert args.seller_country == ["US", "GB"]
    assert args.delivery_days == 3
    assert args.min_price == 20.0 and args.pro is True
    assert args.facet == ["style=retro", "service_offerings=subscription"]
    assert args.order == "price-desc" and args.pages == 2 and args.format == "csv"
    assert args.country == "us"


@pytest.mark.parametrize(
    "argv",
    [
        ["search", "x", "--delivery-days", "2"],
        ["search", "x", "--sort", "price_asc"],
        ["search", "x", "--seller-level", "gold"],
        ["gig"],
    ],
)
def test_parser_rejects_bad_input(argv):
    with pytest.raises(SystemExit):
        build_parser().parse_args(argv)


def test_dry_run_prints_urls_without_calling_the_api(capsys):
    code = main(
        ["search", "logo design", "--seller-level", "top_rated", "--sort", "newest", "--dry-run"]
    )
    assert code == 0
    assert capsys.readouterr().out.strip() == (
        BASE + "&filter=new&ref=seller_level%3Atop_rated_seller"
    )


def test_search_needs_words_or_a_url():
    with pytest.raises(SystemExit):
        main(["search"])


def test_search_to_json_file(tmp_path):
    out = tmp_path / "gigs.json"
    scraper = scraper_for({BASE: page_html(listing_props([card(1), card(2)], has_more=False))})
    code = main(["search", "logo design", "-q", "-o", str(out)], scraper=scraper)
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [row["gig_id"] for row in data] == [1, 2]
    assert data[0]["seller_level"] == "level_two_seller"


def test_search_to_csv_with_local_order(capsys):
    items = [card(1, price_i=50), card(2, price_i=15), card(3, price_i=30)]
    scraper = scraper_for({BASE: page_html(listing_props(items, has_more=False))})
    code = main(["search", "logo design", "-q", "-f", "csv", "--order", "price"], scraper=scraper)
    assert code == 0
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert [row["gig_id"] for row in rows] == ["2", "3", "1"]
    assert rows[0]["seller_languages"] == "en | fr"
    assert rows[0]["attributes"] == "style: flat_minimalist | file_format: png, svg"


def test_search_details_reads_every_gig_page(capsys):
    item = card(777, gig_url="/pixelcraft_studio/design-a-logo-777")
    scraper = scraper_for(
        {
            BASE: page_html(listing_props([item], has_more=False)),
            GIG: page_html(gig_props()),
        }
    )
    code = main(["search", "logo design", "-q", "--details"], scraper=scraper)
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["gig_id"] == 777 and len(data[0]["packages"]) == 3


def test_gig_command_csv_has_one_row_per_package(capsys):
    scraper = scraper_for({GIG: page_html(gig_props())})
    assert main(["gig", GIG, "-q", "-f", "csv"], scraper=scraper) == 0
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert [row["tier"] for row in rows] == ["basic", "standard", "premium"]
    assert rows[0]["price"] == "25.0" and rows[1]["revisions"] == "unlimited"
    assert rows[0]["features"] == "Number of concepts included: 1 | Logo transparency"


def test_gig_command_reports_missing_gigs(capsys):
    scraper = scraper_for({GIG: page_html(seller_props())})
    assert main(["gig", GIG], scraper=scraper) == 1
    assert "FiverrNotFoundError" in capsys.readouterr().err


def test_seller_command_profiles_and_gigs(capsys):
    url = "https://www.fiverr.com/pixelcraft_studio"
    scraper = scraper_for({url: page_html(seller_props())})
    assert main(["seller", "pixelcraft_studio", "-q"], scraper=scraper) == 0
    profile = json.loads(capsys.readouterr().out)[0]
    assert profile["level"] == "top_rated_seller" and len(profile["gigs"]) == 2
    assert (
        main(["seller", "pixelcraft_studio", "-q", "--gigs", "-f", "jsonl"], scraper=scraper) == 0
    )
    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["gig_id"] for line in lines] == [777, 778]


def test_filters_command(capsys):
    scraper = scraper_for({BASE: page_html(listing_props([card(1)]))})
    assert main(["filters", "logo design"], scraper=scraper) == 0
    out = capsys.readouterr().out
    assert "seller_level (Seller level) [multi]" in out
    assert "  top_rated_seller  Top Rated Seller  1,300" in out
    assert "gig_price_range (Budget) use --min-price / --max-price" in out
    assert main(["filters", "logo design", "--json"], scraper=scraper) == 0
    groups = json.loads(capsys.readouterr().out)
    assert groups[0]["key"] == "style"


def test_dropped_filters_exit_with_an_error(capsys):
    url = BASE + "&ref=style%3Abaroque"
    scraper = scraper_for({url: page_html(listing_props([card(1)]))})
    assert main(["search", "logo design", "--facet", "style=baroque", "-q"], scraper=scraper) == 2
    assert "Fiverr did not apply" in capsys.readouterr().err


def test_order_gigs_puts_unknown_values_last():
    gigs = [
        Gig(gig_id=1, title="a", url="u", rating=None),
        Gig(gig_id=2, title="b", url="u", rating=4.5),
        Gig(gig_id=3, title="c", url="u", rating=5.0),
    ]
    assert [g.gig_id for g in order_gigs(gigs, "rating")] == [3, 2, 1]
    assert order_gigs(gigs, None) is gigs
