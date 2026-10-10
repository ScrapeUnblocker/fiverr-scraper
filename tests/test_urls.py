from __future__ import annotations

import pytest

from fiverr_scraper.urls import (
    build_ref,
    decode_ref,
    encode_ref,
    gig_url,
    is_fiverr_url,
    listing_url,
    normalize_sort,
    parse_facets,
    search_url,
    seller_level_value,
    seller_url,
)


def test_search_url_encodes_query_sort_filters_and_page():
    ref = build_ref(seller_level=["top_rated", "level_2"], delivery_days=3)
    url = search_url("  logo   design ", page=2, sort="best_selling", ref=ref)
    assert url == (
        "https://www.fiverr.com/search/gigs?query=logo%20design&filter=rating"
        "&ref=seller_level%3Atop_rated_seller%2Clevel_two_seller%7Cdelivery_time%3A3&page=2"
    )


def test_search_url_first_page_has_no_page_param():
    assert search_url("seo") == "https://www.fiverr.com/search/gigs?query=seo"


def test_search_url_needs_words_and_a_valid_page():
    with pytest.raises(ValueError):
        search_url("   ")
    with pytest.raises(ValueError):
        search_url("seo", page=0)


def test_build_ref_maps_every_friendly_argument():
    ref = build_ref(
        seller_level="new",
        seller_country=["us", "gb"],
        seller_language="EN,de",
        delivery_days=1,
        min_price=19.6,
        max_price=50,
        pro=True,
        online=True,
        agency=True,
        hourly=True,
        facets=["style=retro,flat_minimalist", "service_offerings=subscription"],
    )
    assert ref == {
        "seller_level": ["na"],
        "seller_location": ["US", "GB"],
        "seller_language": ["en", "de"],
        "delivery_time": ["1"],
        "gig_price_range": ["20", "50"],
        "pro": ["any"],
        "is_seller_online": ["true"],
        "is_agency": ["true"],
        "has_hourly": ["true"],
        "style": ["retro", "flat_minimalist"],
        "service_offerings": ["subscription"],
    }


def test_build_ref_open_ended_price_range():
    assert build_ref(min_price=20)["gig_price_range"] == ["20", "50000"]
    assert build_ref(max_price=30)["gig_price_range"] == ["0", "30"]
    with pytest.raises(ValueError):
        build_ref(min_price=60, max_price=10)
    with pytest.raises(ValueError):
        build_ref(min_price=-1)


def test_build_ref_rejects_bad_values():
    with pytest.raises(ValueError):
        build_ref(delivery_days=2)
    with pytest.raises(ValueError):
        build_ref(seller_level="gold")
    with pytest.raises(ValueError):
        build_ref(seller_level="top_rated", facets={"seller_level": "na"})


def test_seller_level_aliases():
    assert seller_level_value("Top Rated") == "top_rated_seller"
    assert seller_level_value("level_two_seller") == "level_two_seller"
    assert seller_level_value("level-1") == "level_one_seller"
    assert seller_level_value("new_seller") == "na"


def test_sort_aliases():
    assert normalize_sort(None) is None
    assert normalize_sort("rating") == "best_selling"
    assert normalize_sort("Best-Selling") == "best_selling"
    assert normalize_sort("new") == "newest"
    with pytest.raises(ValueError):
        normalize_sort("price_asc")


def test_parse_facets_forms():
    assert parse_facets({"style": ["retro", "retro"], "x": ""}) == {"style": ["retro"]}
    assert parse_facets(["style=retro", "style:modern"]) == {"style": ["retro", "modern"]}
    with pytest.raises(ValueError):
        parse_facets(["no-separator"])


def test_ref_round_trip():
    ref = {"seller_level": ["top_rated_seller", "na"], "delivery_time": ["3"]}
    text = encode_ref(ref)
    assert text == "seller_level:top_rated_seller,na|delivery_time:3"
    assert decode_ref(text) == ref
    assert decode_ref(None) == {}


def test_listing_url_keeps_copied_filters_and_replaces_page_and_sort():
    copied = (
        "https://www.fiverr.com/categories/graphics-design/creative-logo-design"
        "?source=gallery-listing&filter=new&ref=seller_location%3AGB&page=3"
    )
    url = listing_url(copied, page=2, sort="best_selling", ref={"delivery_time": ["3"]})
    assert url == (
        "https://www.fiverr.com/categories/graphics-design/creative-logo-design"
        "?source=gallery-listing&filter=rating&ref=seller_location%3AGB%7Cdelivery_time%3A3&page=2"
    )
    # Without a sort the copied one is kept; page 1 drops the page parameter.
    assert listing_url(copied) == (
        "https://www.fiverr.com/categories/graphics-design/creative-logo-design"
        "?source=gallery-listing&filter=new&ref=seller_location%3AGB"
    )


def test_listing_url_rejects_other_pages():
    with pytest.raises(ValueError):
        listing_url("https://www.fiverr.com/pixelcraft_studio")
    with pytest.raises(ValueError):
        listing_url("https://example.com/search/gigs?query=x")


def test_gig_and_seller_urls():
    assert gig_url("pixelcraft_studio/design-a-logo") == (
        "https://www.fiverr.com/pixelcraft_studio/design-a-logo"
    )
    assert gig_url("https://www.fiverr.com/pixelcraft_studio/design-a-logo?context=x") == (
        "https://www.fiverr.com/pixelcraft_studio/design-a-logo"
    )
    assert seller_url("@pixelcraft_studio") == "https://www.fiverr.com/pixelcraft_studio"
    assert seller_url("https://www.fiverr.com/pixelcraft_studio/design-a-logo") == (
        "https://www.fiverr.com/pixelcraft_studio"
    )
    for bad in ("pixelcraft_studio", "https://example.com/a/b", "/search/gigs"):
        with pytest.raises(ValueError):
            gig_url(bad)
    with pytest.raises(ValueError):
        seller_url("https://example.com/someone")


def test_is_fiverr_url():
    assert is_fiverr_url("https://www.fiverr.com/x")
    assert is_fiverr_url("https://fiverr.com/x")
    assert not is_fiverr_url("https://notfiverr.com/x")
    assert not is_fiverr_url(None)
