from __future__ import annotations

import pytest
from conftest import (
    TargetNotFoundError,
    TransientError,
    card,
    gig_props,
    listing_props,
    page_html,
    seller_props,
)

from fiverr_scraper import FiverrFilterError, FiverrNotFoundError, FiverrScraper, Gig
from fiverr_scraper.scraper import check_applied, listing_page_url

BASE = "https://www.fiverr.com/search/gigs?query=logo%20design"
GIG = "https://www.fiverr.com/pixelcraft_studio/design-a-logo-777"


def listing(items, **options):
    return page_html(listing_props(items, **options))


def test_fetch_routes_through_the_country(make_scraper):
    scraper, client = make_scraper({BASE: listing([card(1)])})
    scraper.search_page("logo design")
    assert client.calls == [(BASE, {"proxy_country": "us"})]

    scraper, client = make_scraper({BASE: listing([card(1)])}, country=None)
    scraper.search_page("logo design")
    assert client.calls == [(BASE, {})]


def test_transient_errors_are_retried_with_doubling_backoff(make_scraper):
    retries = []
    scraper, client = make_scraper(
        {BASE: [TransientError("timeout"), TransientError("outage"), listing([card(1)])]},
        on_retry=lambda attempt, delay, error: retries.append((attempt, delay)),
    )
    page = scraper.search_page("logo design")
    assert [g.gig_id for g in page.gigs] == [1]
    assert scraper.sleeps == [1.0, 2.0]
    assert retries == [(1, 1.0), (2, 2.0)]
    assert len(client.calls) == 3


def test_retries_give_up(make_scraper):
    scraper, client = make_scraper({BASE: [TransientError("down")]}, retries=2)
    with pytest.raises(TransientError):
        scraper.search_page("logo design")
    assert len(client.calls) == 3


def test_pages_without_data_are_retried(make_scraper):
    scraper, client = make_scraper({BASE: ["<html>challenge</html>", listing([card(1)])]})
    assert scraper.search_page("logo design").gigs[0].gig_id == 1
    assert len(client.calls) == 2


def test_other_errors_are_not_retried(make_scraper):
    scraper, client = make_scraper({BASE: [RuntimeError("bad key")]})
    with pytest.raises(RuntimeError):
        scraper.search_page("logo design")
    assert len(client.calls) == 1


def test_search_follows_pages_until_only_sponsored_slots_are_left(make_scraper):
    page2 = BASE + "&page=2"
    page3 = BASE + "&page=3"
    scraper, client = make_scraper(
        {
            BASE: listing([card(1, type="promoted_gigs"), card(2), card(3)]),
            page2: listing([card(1, type="promoted_gigs"), card(4)], page=2),
            page3: listing([card(1, type="promoted_gigs"), card(2, type="promoted_gigs")], page=3),
        }
    )
    gigs = scraper.search("logo design", pages=5)
    assert [g.gig_id for g in gigs] == [1, 2, 3, 4]
    assert client.urls == [BASE, page2, page3]
    assert all(g.query == "logo design" for g in gigs)


def test_search_stops_when_fiverr_has_no_more_results(make_scraper):
    scraper, client = make_scraper({BASE: listing([card(1), card(2)], has_more=False)})
    assert len(scraper.search("logo design", pages=3)) == 2
    assert client.urls == [BASE]


def test_search_limit_and_local_filters(make_scraper):
    items = [
        card(1, type="promoted_gigs"),
        card(2, buying_review_rating=4.2),
        card(3, buying_review_rating_count=3),
        card(4),
        card(5),
    ]
    scraper, _ = make_scraper({BASE: listing(items, has_more=False)})
    gigs = scraper.search(
        "logo design", skip_sponsored=True, min_rating=4.5, min_reviews=10, limit=1
    )
    assert [g.gig_id for g in gigs] == [4]


def test_search_many_dedupes_across_queries(make_scraper):
    other = "https://www.fiverr.com/search/gigs?query=brand%20identity"
    scraper, _ = make_scraper(
        {
            BASE: listing([card(1), card(2)], has_more=False),
            other: listing([card(2), card(3)], has_more=False, query="brand identity"),
        }
    )
    seen_per_query = []
    gigs = scraper.search_many(
        ["logo design", "brand identity"], on_query=lambda q, found: seen_per_query.append(q)
    )
    assert [g.gig_id for g in gigs] == [1, 2, 3]
    assert gigs[2].query == "brand identity"
    assert seen_per_query == ["logo design", "brand identity"]


def test_search_sends_filters(make_scraper):
    url = listing_page_url(
        "logo design", sort="best_selling", seller_level=["top_rated"], delivery_days=3
    )
    assert url == (BASE + "&filter=rating&ref=seller_level%3Atop_rated_seller%7Cdelivery_time%3A3")
    scraper, client = make_scraper({url: listing([card(1)], sort="rating", has_more=False)})
    scraper.search("logo design", sort="best_selling", seller_level=["top_rated"], delivery_days=3)
    assert client.urls == [url]


def test_unknown_keyword_filters_are_rejected(make_scraper):
    scraper, _ = make_scraper({})
    with pytest.raises(TypeError):
        scraper.search("logo design", colour="red")


def test_check_applied_catches_dropped_sort_and_unknown_filters():
    from fiverr_scraper.parsing import parse_search_page

    page = parse_search_page(listing([card(1)], sort="auto"), BASE)
    check_applied(page, None, seller_level="top_rated", facets=["style=retro"], pro=True)
    with pytest.raises(FiverrFilterError, match="sort=newest"):
        check_applied(page, "newest")
    with pytest.raises(FiverrFilterError, match="no such filter"):
        check_applied(page, None, facets=["colour=red"])
    with pytest.raises(FiverrFilterError, match="offered here"):
        check_applied(page, None, facets=["style=baroque"])
    with pytest.raises(FiverrFilterError, match="seller_location=FR"):
        check_applied(page, None, seller_country=["US", "FR"])


def test_search_page_raises_on_dropped_filters_unless_disabled(make_scraper):
    url = BASE + "&ref=style%3Abaroque"
    scraper, _ = make_scraper({url: listing([card(1)])})
    with pytest.raises(FiverrFilterError):
        scraper.search_page("logo design", facets={"style": "baroque"})
    page = scraper.search_page("logo design", facets={"style": "baroque"}, check_filters=False)
    assert len(page.gigs) == 1


def test_filters_reads_one_page(make_scraper):
    scraper, client = make_scraper({BASE: listing([card(1)])})
    page = scraper.filters("logo design")
    assert page.filter_group("seller_level") is not None
    assert client.urls == [BASE]


def test_gig_accepts_urls_paths_and_search_results(make_scraper):
    scraper, client = make_scraper({GIG: page_html(gig_props())})
    assert scraper.gig(GIG + "?context_referrer=search").gig_id == 777
    assert scraper.gig("pixelcraft_studio/design-a-logo-777").packages[0].price == 25.0
    found = Gig(gig_id=777, title="t", url=GIG)
    assert scraper.gig(found).seller.username == "pixelcraft_studio"
    assert client.urls == [GIG, GIG, GIG]


def test_missing_gig_is_not_found_and_not_retried(make_scraper):
    scraper, client = make_scraper({GIG: page_html(seller_props())})
    with pytest.raises(FiverrNotFoundError):
        scraper.gig(GIG)
    assert len(client.calls) == 1


def test_gigs_collects_failures(make_scraper):
    gone = "https://www.fiverr.com/pixelcraft_studio/gone"
    scraper, _ = make_scraper({GIG: page_html(gig_props()), gone: page_html(seller_props())})
    errors = []
    details = scraper.gigs([GIG, gone], on_error=lambda item, exc: errors.append(item))
    assert [d.gig_id for d in details] == [777]
    assert errors == [gone]
    with pytest.raises(FiverrNotFoundError):
        scraper.gigs([gone])


def test_seller_profile_and_404(make_scraper):
    profile_url = "https://www.fiverr.com/pixelcraft_studio"
    missing = "https://www.fiverr.com/nobody_here"
    scraper, client = make_scraper(
        {profile_url: page_html(seller_props()), missing: TargetNotFoundError("404")}
    )
    assert scraper.seller("pixelcraft_studio").level == "top_rated_seller"
    assert scraper.seller(GIG).username == "pixelcraft_studio"
    with pytest.raises(FiverrNotFoundError):
        scraper.seller("nobody_here")
    assert client.urls.count(missing) == 1


def test_default_client_reads_the_sdk(monkeypatch):
    created = {}

    class Client:
        def __init__(self, api_key=None, timeout=None):
            created.update(api_key=api_key, timeout=timeout)

    import scrapeunblocker

    monkeypatch.setattr(scrapeunblocker, "Client", Client)
    FiverrScraper(api_key="test-key", timeout=30)
    assert created == {"api_key": "test-key", "timeout": 30}
