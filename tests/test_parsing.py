from __future__ import annotations

import pytest
from conftest import card, gig_props, listing_props, page_html, seller_props

from fiverr_scraper.parsing import (
    FiverrNotFoundError,
    FiverrParseError,
    cents,
    epoch_date,
    epoch_ms_iso,
    extract_props,
    hours_to_days,
    html_to_text,
    language_level,
    normalize_level,
    parse_gig_page,
    parse_search_page,
    parse_seller_page,
)

URL = "https://www.fiverr.com/search/gigs?query=logo%20design"


def test_extract_props_requires_the_embedded_document():
    with pytest.raises(FiverrParseError):
        extract_props("<html><body>Please verify you are a human</body></html>")
    with pytest.raises(FiverrParseError):
        extract_props('<script id="perseus-initial-props" type="application/json">{oops</script>')
    assert extract_props(page_html({"a": 1})) == {"a": 1}


def test_search_page_metadata():
    page = parse_search_page(page_html(listing_props([card(1)], sort="rating", page=2)), URL)
    assert page.page == 2
    assert page.sort == "best_selling"
    assert page.total == 179000
    assert page.has_more is True
    assert page.page_size == 48
    assert page.category == "Graphics & Design"
    assert page.sub_category == "Logo Design"
    assert page.sub_category_id == 49
    assert page.query == "logo design"
    assert page.currency == "USD"


def test_gig_card_fields():
    item = card(
        42,
        hourly_rate=3500,
        seller_level="",
        recurring_options=[{"discount_percentage": 10}, {"discount_percentage": 20}],
        attachments=[{"stream_url": "https://example.com/v.mp4"}],
        agency={"slug": "studio-agency"},
        offer_consultation=True,
    )
    gig = parse_search_page(page_html(listing_props([item])), URL).gigs[0]
    assert gig.gig_id == 42
    assert gig.url == "https://www.fiverr.com/pixelcraft_studio/design-a-logo-42"
    assert gig.price == 25.0
    assert gig.currency == "USD"
    assert gig.delivery_days == 3
    assert gig.packages == 3
    assert gig.hourly_rate == 35.0
    assert gig.rating == 4.9 and gig.reviews == 120
    assert gig.seller_username == "pixelcraft_studio"
    assert gig.seller_name == "Pixel Craft"
    assert gig.seller_level == "new_seller"
    assert gig.seller_rating == 4.88 and gig.seller_reviews == 340
    assert gig.seller_languages == ["en", "fr"]
    assert gig.seller_url == "https://www.fiverr.com/pixelcraft_studio"
    assert gig.agency == "studio-agency"
    assert gig.offers_consultation is True
    assert gig.offers_subscription is True and gig.subscription_discount == 20
    assert gig.attributes == {"style": ["flat_minimalist"], "file_format": ["png", "svg"]}
    assert gig.image == "https://example.com/42/1.jpg" and len(gig.images) == 2
    assert gig.video == "https://example.com/v.mp4"
    assert gig.nested_sub_category_id is None
    assert gig.position == 1 and gig.page == 1 and gig.query == "logo design"


def test_sponsored_duplicates_keep_the_organic_card():
    items = [
        card(1, type="promoted_gigs"),
        card(2, type="promoted_gigs"),
        card(3),
        card(1),
        card(4, type="fiverr_choice"),
        card(5, type="pro", is_pro=False),
        {"gigId": None, "title": "broken"},
    ]
    page = parse_search_page(page_html(listing_props(items)), URL)
    assert [g.gig_id for g in page.gigs] == [2, 3, 1, 4, 5]
    by_id = {g.gig_id: g for g in page.gigs}
    assert by_id[1].sponsored is False and by_id[1].position == 4
    assert by_id[2].sponsored is True
    assert by_id[4].fiverr_choice is True
    assert by_id[5].pro is True
    assert [g.gig_id for g in page.organic] == [3, 1, 4, 5]


def test_price_falls_back_to_the_recommended_package():
    item = card(9, price_i=None)
    item["packages"]["recommended"]["price"] = 40
    assert parse_search_page(page_html(listing_props([item])), URL).gigs[0].price == 40.0


def test_filter_groups():
    page = parse_search_page(page_html(listing_props([card(1)])), URL)
    keys = [group.key for group in page.filters]
    assert keys == [
        "style",
        "seller_level",
        "seller_location",
        "delivery_time",
        "gig_price_range",
        "pro",
    ]
    style = page.filter_group("style")
    assert style is not None and style.multi and style.values == ["flat_minimalist", "retro"]
    assert style.options[0].label == "Minimalist" and style.options[0].count == 55000
    delivery = page.filter_group("delivery_time")
    assert delivery is not None and delivery.values == ["1", "3", "7"]
    assert page.filter_group("gig_price_range").options == []  # type: ignore[union-attr]
    assert page.filter_group("pro").values == ["any"]  # type: ignore[union-attr]


def test_search_page_requires_items():
    with pytest.raises(FiverrParseError):
        parse_search_page(page_html({"seller": {}}), URL)


def test_gig_page_packages():
    details = parse_gig_page(page_html(gig_props()), "https://www.fiverr.com/x/y")
    basic, standard, premium = details.packages
    assert basic.tier == "basic" and basic.name == "BASIC"
    assert basic.price == 25.0 and basic.delivery_days == 3
    assert basic.revisions == 2
    assert basic.features == ["Number of concepts included: 1", "Logo transparency"]
    assert basic.extra_fast_price == 15.0 and basic.extra_fast_days == 1
    assert standard.price == 60.0 and standard.delivery_days == 1.5
    assert standard.revisions == "unlimited"
    assert standard.extra_fast_price is None and standard.extra_fast_days is None
    assert premium.tier == "premium" and premium.name == "PREMIUM"
    assert premium.revisions == 0
    assert details.package("Standard") is standard
    assert details.price_min == 25.0 and details.price_max == 120.0


def test_gig_page_details():
    details = parse_gig_page(page_html(gig_props()), "https://www.fiverr.com/x/y")
    assert details.gig_id == 777
    assert details.title == "design a modern minimalist logo"
    assert details.url == "https://www.fiverr.com/pixelcraft_studio/design-a-logo-777"
    assert details.rating == 4.9 and details.reviews_count == 120
    assert details.star_counts == {"5": 110, "4": 9, "1": 1}
    assert details.rating_breakdown == {"communication": 5.0, "quality": 4.9, "value": 4.8}
    assert details.orders_in_queue == 7 and details.favorites == 950
    assert details.category == "Graphics & Design" and details.sub_category == "Logo Design"
    assert details.description == "Hello! I design logos.\n\n- Fast\n- Clean & modern"
    assert details.attributes == {"Logo style": ["Minimalist"]}
    assert details.faq == [{"question": "What do you need?", "answer": "Your brand name."}]
    assert details.tags == ["logo", "brand identity"]
    assert details.ai_summary == ["Clean minimalist logos."]
    assert details.images == ["https://example.com/g/1.jpg", "https://example.com/g/2.png"]
    assert details.subscription_discounts == [
        {"duration": 3, "unit": "month", "discount_percent": 10}
    ]
    assert details.consultation == [{"minutes": 30, "price": 40.0}]
    assert details.other_gig_ids == [778, 779]
    review = details.reviews[0]
    assert review.rating == 5.0 and review.comment == "Great work, fast."
    assert review.reviewer == "happy_buyer" and review.reviewer_country_code == "US"
    assert review.order_price_range == "Up to $50" and review.order_duration_days == 3
    assert review.repeat_buyer is True and review.seller_response == "Thank you!"


def test_gig_page_seller():
    seller = parse_gig_page(page_html(gig_props()), "https://www.fiverr.com/x/y").seller
    assert seller.username == "pixelcraft_studio"
    assert seller.name == "Pixel Craft"
    assert seller.seller_id == 1001
    assert seller.url == "https://www.fiverr.com/pixelcraft_studio"
    assert seller.country_code == "GB"
    assert seller.level == "level_two_seller"
    assert seller.rating == 4.9 and seller.reviews == 340
    assert seller.member_since == "2018-10-01"
    assert seller.response_hours == 1
    assert seller.completed_orders == 512
    assert seller.last_delivery == "2026-10-10T08:04:10Z"
    assert seller.languages == [{"code": "en", "level": "native_or_bilingual"}]
    assert seller.one_liner == "Brand designer"
    assert seller.verified is True and seller.highly_responsive is True


def test_missing_gig_shows_the_seller_profile():
    with pytest.raises(FiverrNotFoundError):
        parse_gig_page(page_html(seller_props()), "https://www.fiverr.com/x/gone")
    with pytest.raises(FiverrParseError):
        parse_gig_page(page_html(listing_props([])), "https://www.fiverr.com/x/y")


def test_seller_page():
    profile = parse_seller_page(page_html(seller_props()), "https://www.fiverr.com/x")
    assert profile.username == "pixelcraft_studio"
    assert profile.url == "https://www.fiverr.com/pixelcraft_studio"
    assert profile.name == "Pixel Craft" and profile.seller_id == 1001
    assert profile.country == "United Kingdom" and profile.country_code == "GB"
    assert profile.timezone == "Europe/London"
    assert profile.member_since == "2018-10-01"
    assert profile.level == "top_rated_seller"
    assert profile.rating == 4.9 and profile.reviews_count == 340
    assert profile.star_counts == {"5": 300}
    assert profile.rating_breakdown == {"communication": 4.9}
    assert profile.languages == [{"code": "en", "level": "fluent"}]
    assert profile.skills == [{"name": "Logo design", "level": "pro"}]
    assert profile.education[0] == {
        "school": "Uni",
        "degree": "BA",
        "field": "Graphic design",
        "year": 2014,
        "country_code": "GB",
    }
    assert profile.certifications == [{"name": "ACP", "issuer": "Adobe", "year": 2019}]
    assert profile.gigs_count == 2 and [g.gig_id for g in profile.gigs] == [777, 778]
    assert profile.reviews[0].reviewer == "buyer9"


def test_seller_page_rejects_gig_pages():
    with pytest.raises(FiverrParseError):
        parse_seller_page(page_html(gig_props()), "https://www.fiverr.com/x")


@pytest.mark.parametrize(
    ("raw", "level"),
    [
        ("top_rated_seller", "top_rated_seller"),
        ("LEVEL_TRS", "top_rated_seller"),
        ("TOP_RATED_SELLER", "top_rated_seller"),
        ("level_two_seller", "level_two_seller"),
        ("LEVEL_TWO", "level_two_seller"),
        ("level_one_seller", "level_one_seller"),
        ("", "new_seller"),
        ("na", "new_seller"),
        (None, None),
    ],
)
def test_normalize_level(raw, level):
    assert normalize_level(raw) == level


def test_value_helpers():
    assert cents(2500) == 25.0 and cents(None) is None
    assert hours_to_days(72) == 3 and hours_to_days(36) == 1.5 and hours_to_days(0) is None
    assert language_level(3) == "fluent" and language_level("BASIC") == "basic"
    assert language_level("4") == "native_or_bilingual"
    assert epoch_date(0) is None and epoch_date(1538394513) == "2018-10-01"
    assert epoch_ms_iso(1791619450000) == "2026-10-10T08:04:10Z"
    assert html_to_text("<p>a<br>b</p>") == "a\nb"
    assert html_to_text(None) is None
