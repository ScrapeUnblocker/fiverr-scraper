"""Shared fixtures: synthetic Fiverr pages and a fake ScrapeUnblocker client.

The page data mirrors the shape of the JSON Fiverr embeds in its pages
(``<script id="perseus-initial-props">``), trimmed to the fields the parsers
read. No network access and no API credit are needed to run the tests.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

import pytest


def page_html(props: dict[str, Any]) -> str:
    """A minimal Fiverr page carrying ``props`` the way Fiverr embeds them."""
    payload = json.dumps(props)
    return (
        "<!DOCTYPE html><html><head><title>Fiverr</title></head><body>"
        '<div id="perseus-app"></div>'
        '<script id="perseus-initial-props" type="application/json">'
        f"{payload}</script></body></html>"
    )


def card(gig_id: int, **overrides: Any) -> dict[str, Any]:
    """One gig card of a listing."""
    base: dict[str, Any] = {
        "gigId": gig_id,
        "gig_id": gig_id,
        "pos": 0,
        "is_fiverr_choice": False,
        "packages": {"recommended": {"id": 1, "price": 25, "duration": 3, "type": "cheapest"}},
        "sellerId": "1001",
        "category_id": 3,
        "sub_category_id": 49,
        "nested_sub_category_id": 0,
        "is_pro": False,
        "is_featured": False,
        "cached_slug": f"design-a-logo-{gig_id}",
        "title": f"design a modern minimalist logo {gig_id}",
        "seller_name": "pixelcraft_studio",
        "seller_id": 1001,
        "seller_country": "GB",
        "seller_img": "https://example.com/avatar.jpg",
        "seller_display_name": "Pixel Craft",
        "seller_online": True,
        "status": "APPROVED",
        "offer_consultation": False,
        "assets": [
            {"cloud_img_main_gig": f"https://example.com/{gig_id}/1.jpg", "type": "ImageAsset"},
            {"cloud_img_main_gig": f"https://example.com/{gig_id}/2.jpg", "type": "ImageAsset"},
        ],
        "seller_languages": [{"code": "en", "level": 4}, {"code": "fr", "level": 2}],
        "recurring_options": [],
        "metadata": [
            {"type": "style", "value": ["flat_minimalist"]},
            {"type": "file_format", "value": ["png", "svg"]},
        ],
        "has_recurring_option": False,
        "buying_review_rating_count": 120,
        "buying_review_rating": 4.9,
        "seller_url": "/pixelcraft_studio",
        "seller_level": "level_two_seller",
        "seller_rating": {"count": 340, "score": 4.876},
        "gig_url": f"/pixelcraft_studio/design-a-logo-{gig_id}",
        "price_i": 25,
        "num_of_packages": 3,
    }
    base.update(overrides)
    return base


def filter_groups() -> list[dict[str, Any]]:
    return [
        {
            "id": "style",
            "display_type": "checkbox_group",
            "selector": "multi",
            "alias": "Logo style",
            "options": [
                {"id": "flat_minimalist", "alias": "Minimalist", "count": 55000},
                {"id": "retro", "alias": "Vintage", "count": 24000},
            ],
        },
        {
            "id": "seller_level",
            "display_type": "checkbox_group",
            "selector": "multi",
            "alias": "Seller level",
            "options": [
                {"id": "top_rated_seller", "alias": "Top Rated Seller", "count": 1300},
                {"id": "level_two_seller", "alias": "Level 2", "count": 11000},
                {"id": "level_one_seller", "alias": "Level 1", "count": 9400},
                {"id": "na", "alias": "New Seller", "count": 150000},
            ],
        },
        {
            "id": "seller_location",
            "display_type": "checkbox_group",
            "selector": "multi",
            "alias": "Seller lives in",
            "options": [
                {"id": "US", "alias": "United States", "count": 30000},
                {"id": "GB", "alias": "United Kingdom", "count": 41000},
            ],
        },
        {
            "id": "delivery_time",
            "display_type": "radio",
            "selector": "single",
            "alias": "Delivery time",
            "options": [
                {"id": "1", "alias": "Express 24H"},
                {"id": "3", "alias": "Up to 3 days"},
                {"id": "7", "alias": "Up to 7 days"},
                {"id": "", "alias": "Anytime", "selected": True},
            ],
        },
        {
            "id": "gig_price_range",
            "display_type": "input_range",
            "selector": "single",
            "alias": "Budget",
            "options": [{"id": "gig_price_range_option"}],
        },
        {
            "id": "pro",
            "display_type": "pro",
            "selector": "single",
            "alias": "Pro services",
            "options": [{"id": "pro", "count": 400}],
        },
    ]


def listing_props(
    items: list[dict[str, Any]],
    *,
    page: int = 1,
    sort: str = "auto",
    total: int = 179000,
    has_more: bool = True,
    active: dict[str, Any] | None = None,
    query: str = "logo design",
) -> dict[str, Any]:
    return {
        "listingQuery": query,
        "flow": "search",
        "currency": {"name": "USD", "rate": 1, "symbol": "$"},
        "activeFilters": active or {},
        "appData": {
            "pagination": {"page": page, "offset": -20, "page_size": 48, "total": total},
            "sorting": {"sortBy": sort},
        },
        "rawListingData": {"num_found": total, "has_more": has_more},
        "displayData": {"categoryName": "Graphics & Design", "subCategoryName": "Logo Design"},
        "subCategoryData": {
            "id": 49,
            "name": "Logo Design",
            "category": {"id": 3, "name": "Graphics & Design"},
        },
        "appFilters": {"filters": filter_groups()},
        "items": items,
    }


def gig_props() -> dict[str, Any]:
    package = {
        "id": 1,
        "title": "BASIC",
        "description": "One logo concept + PNG",
        "price": 2500,
        "duration": 72,
        "revisions": {"name": "modifications", "included": True, "value": 2},
        "extraFast": {"name": "extra_fast", "included": False, "duration": 24, "price": 1500},
        "features": [
            {
                "label": "Number of concepts included",
                "included": True,
                "value": 1,
                "type": "NUMERIC",
            },
            {"label": "Logo transparency", "included": True, "value": 0, "type": "BOOLEAN"},
            {"label": "Vector file", "included": False, "value": 0, "type": "BOOLEAN"},
        ],
    }
    standard = copy.deepcopy(package)
    standard.update(
        {
            "id": 2,
            "title": "STANDARD",
            "price": 6000,
            "duration": 36,
            "revisions": {"name": "modifications", "included": True, "value": -1},
            "extraFast": {"included": False, "duration": 0, "price": 0},
        }
    )
    premium = copy.deepcopy(package)
    premium.update(
        {
            "id": 3,
            "title": "PREMIUM  ",
            "price": 12000,
            "duration": 120,
            "revisions": {"name": "modifications", "included": False, "value": 0},
        }
    )
    return {
        "general": {
            "gigId": 777,
            "categoryName": "Graphics & Design",
            "categorySlug": "graphics-design",
            "subCategoryName": "Logo Design",
            "subCategorySlug": "creative-logo-design",
            "nestedSubCategorySlug": None,
            "isPro": False,
            "gigTitle": "design a modern minimalist logo",
        },
        "overview": {
            "gig": {"id": 777, "rating": 4.9, "ratingsCount": 120, "ordersInQueue": 7},
            "categories": {"nestedSubCategory": None},
        },
        "topNav": {"gigCollectedCount": 950},
        "sellerCard": {
            "oneLiner": "Brand designer",
            "rating": 4.9,
            "ratingsCount": 340,
            "countryCode": "GB",
            "memberSince": 1538394513,
            "responseTime": 2,
            "recentDelivery": 1791619450000,
            "proficientLanguages": [{"name": "en", "level": 4}],
        },
        "seo": {
            "description": {"sellerAchievement": "level_two_seller"},
            "schemaMarkup": {"gigOffers": {"lowPrice": "25.00", "highPrice": "120.00"}},
        },
        "description": {
            "content": "<p><strong>Hello!</strong> I design logos.</p><ul><li>Fast</li>"
            "<li>Clean &amp; modern</li></ul>",
            "metadataAttributes": [
                {
                    "name": "style",
                    "options": [{"value": "flat_minimalist", "label": "Minimalist"}],
                    "metadata": {"name": "style", "alias": "Logo style"},
                }
            ],
        },
        "gallery": {
            "slides": [
                {"slide": {"src": "https://example.com/g/1.jpg"}},
                {"slide": {"src": "https://example.com/g/brochure.pdf"}},
                {"slide": {"src": "https://example.com/video/upload/clip"}},
                {"slide": {"src": "https://example.com/g/2.png"}},
            ]
        },
        "faq": {
            "questionsAndAnswers": [
                {"question": "What do you need?", "answer": "Your brand name."},
                {"question": "", "answer": "ignored"},
            ]
        },
        "packages": {
            "packageList": [package, standard, premium],
            "recurringOptions": [
                {"discountPercentage": 10, "duration": 3, "durationTimeUnit": "time_unit_month"}
            ],
        },
        "tags": {"tagsGigList": [{"name": "logo"}, {"name": "brand identity"}]},
        "portfolio": {"slug": "design-a-logo-777", "username": "pixelcraft_studio"},
        "otherGigs": {"gigIds": [778, 779]},
        "consultationData": {
            "pricing": [
                {"session_minutes": 30, "price": 40, "status": "ACTIVE"},
                {"session_minutes": 60, "price": 70, "status": "DISABLED"},
            ]
        },
        "aiSummary": {"summary": ["Clean minimalist logos."], "visible": True},
        "reviews": {
            "average_valuation": 4.9,
            "total_count": 120,
            "breakdown": [
                {"average_valuation_value": 1, "count": 1},
                {"average_valuation_value": 5, "count": 110},
                {"average_valuation_value": 4, "count": 9},
            ],
            "star_summary": {
                "communication_valuation": 5,
                "quality_of_delivery_valuation": 4.9,
                "value_for_money_valuation": 4.8,
            },
            "reviews": [
                {
                    "id": "r1",
                    "value": 5,
                    "comment": "  Great work, fast.\n\n",
                    "username": "happy_buyer",
                    "reviewer_country": "United States",
                    "reviewer_country_code": "US",
                    "created_at": "2026-09-05T15:05:48",
                    "order_price_range_usd": "Up to $50",
                    "order_duration_in_days": 3,
                    "repeat_buyer": True,
                    "is_business": False,
                    "seller_response": {"comment": "Thank you!"},
                    "gig_id": 777,
                }
            ],
        },
        "seller": {
            "user": {
                "name": "pixelcraft_studio",
                "id": "1001",
                "profile": {"displayName": "Pixel Craft"},
                "languages": [{"code": "EN", "level": "NATIVE_OR_BILINGUAL"}],
                "address": {"countryCode": "GB"},
                "joinedAt": 1538394513,
            },
            "sellerLevel": "LEVEL_TWO",
            "rating": {"count": 340, "score": 4.9},
            "responseTime": {"inHours": 1},
            "id": "1001",
            "completedOrdersCount": 512,
            "isVerified": True,
            "isHighlyResponsive": True,
            "isOnVacation": False,
            "isPro": False,
            "description": "Designer for 10 years.",
            "oneLinerTitle": None,
        },
    }


def seller_props() -> dict[str, Any]:
    return {
        "seller": {
            "user": {
                "id": "1001",
                "name": "pixelcraft_studio",
                "joinedAt": 1538394513,
                "profile": {"displayName": "Pixel Craft"},
                "address": {"countryName": "United Kingdom", "countryCode": "GB"},
                "languages": [{"code": "EN", "level": "FLUENT"}],
                "localization": {"timezone": "Europe/London"},
                "profileImageUrl": "https://example.com/avatar.jpg",
            },
            "approvedGigsCount": 2,
            "agency": None,
            "oneLinerTitle": "Brand designer",
            "description": "Designer for 10 years.",
            "isVerified": False,
            "isHighlyResponsive": True,
            "certifications": [{"receivedFrom": "Adobe", "certificationName": "ACP", "year": 2019}],
            "activeEducations": [
                {
                    "degree": "Graphic design",
                    "toYear": 2014,
                    "countryCode": "GB",
                    "school": "Uni",
                    "degreeTitle": "BA",
                }
            ],
            "activeStructuredSkills": [{"name": "Logo design", "level": "PRO"}],
            "isPro": False,
            "rating": {"score": 4.9, "count": 340},
            "isOnVacation": False,
            "achievementLevel": "TOP_RATED_SELLER",
            "sellerLevel": "LEVEL_TRS",
            "responseTime": {"inHours": 1},
        },
        "localizationData": {"timezone": "Europe/London"},
        "reviewsData": {
            "buying_reviews": {
                "reviews": [{"id": "r9", "value": 4, "comment": "Good", "username": "buyer9"}],
                "total_count": 340,
                "breakdown": [{"average_valuation_value": 5, "count": 300}],
                "star_summary": {"communication_valuation": 4.9},
            }
        },
        "gigsData": [card(777), card(778, title="design a vintage badge logo")],
    }


class FakeClient:
    """Stands in for ``scrapeunblocker.Client``: answers from a URL -> response map.

    A response may be HTML, an exception instance (raised) or a list of those
    (consumed one per call, the last one repeating). A callable gets the URL.
    """

    def __init__(self, responses: dict[str, Any] | Callable[[str], Any] | None = None) -> None:
        self.responses = responses if responses is not None else {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_page_source(self, url: str, **options: Any) -> Any:
        self.calls.append((url, options))
        if callable(self.responses):
            answer = self.responses(url)
        else:
            if url not in self.responses:
                raise AssertionError(f"unexpected URL fetched: {url}")
            answer = self.responses[url]
            if isinstance(answer, list):
                answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, BaseException):
            raise answer
        return answer

    @property
    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]


class TransientError(Exception):
    """Plays the part of a retryable SDK error (timeouts, outages, ...)."""


class TargetNotFoundError(Exception):
    """Same class name as the SDK's 404 error, which the scraper maps to not-found."""


@pytest.fixture
def make_scraper():
    from fiverr_scraper import FiverrScraper

    def build(responses: Any, **options: Any):
        client = FakeClient(responses)
        sleeps: list[float] = []
        options.setdefault("transient_errors", (TransientError,))
        options.setdefault("backoff", 1.0)
        scraper = FiverrScraper(client=client, sleep=sleeps.append, **options)
        scraper.sleeps = sleeps  # type: ignore[attr-defined]
        return scraper, client

    return build
