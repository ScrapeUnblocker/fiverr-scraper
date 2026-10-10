"""Scrape Fiverr through the ScrapeUnblocker ``getPageSource`` API.

:class:`FiverrScraper` fetches Fiverr search and category listings, gig pages
and seller profiles as rendered HTML and parses the data Fiverr embeds in
them. Timeouts, transient API errors and pages that come back without their
data are retried with doubling backoff, so a long collection run keeps going.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, Callable, TypeVar

from .models import Gig, GigDetails, SearchPage, SellerProfile
from .parsing import (
    FiverrFilterError,
    FiverrNotFoundError,
    FiverrParseError,
    parse_gig_page,
    parse_search_page,
    parse_seller_page,
)
from .urls import (
    SORTS,
    build_ref,
    gig_url,
    is_fiverr_url,
    is_listing_url,
    listing_url,
    normalize_sort,
    search_url,
    seller_url,
)

T = TypeVar("T")

_TRANSIENT_NAMES = (
    "UpstreamOutageError",
    "RateLimitError",
    "ScrapeTimeoutError",
    "BrowserTimeoutError",
    "BlockedError",
    "ServerError",
    "ConnectionError",
)
_NOT_FOUND_NAMES = ("TargetNotFoundError", "NotFoundError")

#: Keyword filters accepted by the search methods (see :func:`fiverr_scraper.urls.build_ref`).
FILTERS = (
    "seller_level",
    "seller_country",
    "seller_language",
    "delivery_days",
    "min_price",
    "max_price",
    "pro",
    "online",
    "agency",
    "hourly",
    "facets",
)

#: Filters whose values are not checked against the options a listing offers.
_FREE_VALUES = {"gig_price_range", "pro", "delivery_time"}


def _transient_errors() -> tuple[type[BaseException], ...]:
    """Best-effort tuple of ScrapeUnblocker exceptions worth retrying.

    Imported lazily so the package is usable (and unit-testable) even when the
    ``scrapeunblocker`` SDK is not installed.
    """
    try:
        import scrapeunblocker  # type: ignore
    except Exception:  # pragma: no cover - depends on SDK availability
        return ()
    found = (getattr(scrapeunblocker, name, None) for name in _TRANSIENT_NAMES)
    return tuple(cls for cls in found if isinstance(cls, type))


def _is_not_found(error: BaseException) -> bool:
    return any(cls.__name__ in _NOT_FOUND_NAMES for cls in type(error).__mro__)


def _check_filters(filters: Mapping[str, Any]) -> None:
    unknown = set(filters) - set(FILTERS)
    if unknown:
        raise TypeError(f"unknown search filter(s): {', '.join(sorted(unknown))}")


def listing_page_url(
    query: str | None = None,
    *,
    url: str | None = None,
    page: int = 1,
    sort: str | None = None,
    **filters: Any,
) -> str:
    """The URL of one page of results, from search words or a copied listing URL.

    ``url`` may be any Fiverr search or category URL copied from the browser
    (filters already in it are kept); ``page``, ``sort`` and the given filters
    are applied to it.
    """
    _check_filters(filters)
    ref = build_ref(**filters)
    if url:
        if query:
            raise ValueError("give search words or a url, not both")
        if not is_fiverr_url(url) or not is_listing_url(url):
            raise ValueError(f"not a Fiverr search or category URL: {url!r}")
        return listing_url(url, page=page, sort=sort, ref=ref)
    return search_url(query or "", page=page, sort=sort, ref=ref)


def check_applied(page: SearchPage, sort: str | None = None, **filters: Any) -> None:
    """Raise :class:`FiverrFilterError` when the page shows that a requested sort
    order or filter was not applied.

    Fiverr echoes every ``ref`` filter back, even one it does not know, so
    filters are checked against the filters the listing actually offers: an
    unknown filter name, or a value that is not one of its options, is an error.
    """
    _check_filters(filters)
    problems: list[str] = []
    wanted_sort = normalize_sort(sort)
    if wanted_sort and page.sort != wanted_sort:
        problems.append(f"sort={wanted_sort} (the page is sorted by {page.sort})")
    offered = {group.key: group for group in page.filters}
    if offered:
        for key, values in build_ref(**filters).items():
            group = offered.get(key)
            if group is None:
                problems.append(f"{key} (this listing has no such filter)")
                continue
            if key in _FREE_VALUES or not group.options:
                continue
            known = set(group.values)
            missing = [value for value in values if value not in known]
            if missing:
                sample = ", ".join(group.values[:12])
                problems.append(f"{key}={','.join(missing)} (offered here: {sample})")
    if problems:
        raise FiverrFilterError(f"Fiverr did not apply: {'; '.join(problems)} (url: {page.url})")


class FiverrScraper:
    """Search Fiverr gigs and read gig pages and seller profiles.

    Args:
        api_key: ScrapeUnblocker key. If omitted, the SDK reads
            ``SCRAPEUNBLOCKER_KEY`` from the environment.
        client: A pre-built client (or any object exposing
            ``get_page_source(url, proxy_country=...)``). Mainly for testing.
        country: Country the requests are routed through (default ``us``).
            Fiverr ranks gigs for the visitor's country; prices stay in USD.
        retries: Extra attempts per request on transient failures.
        backoff: Seconds before the first retry; doubles on every further retry.
        max_backoff: Upper bound for a single wait between retries.
        timeout: Per-request timeout passed to the SDK client.
        transient_errors: Exception classes treated as retryable. Defaults to
            the ScrapeUnblocker transient set.
        on_retry: Optional callback ``(attempt, delay_seconds, error)`` invoked
            before every retry (handy for progress output).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any | None = None,
        country: str | None = "us",
        retries: int = 3,
        backoff: float = 5.0,
        max_backoff: float = 60.0,
        timeout: float = 180.0,
        transient_errors: Sequence[type[BaseException]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        on_retry: Callable[[int, float, BaseException], None] | None = None,
    ) -> None:
        if client is None:
            from scrapeunblocker import Client  # local import: optional dep

            client = Client(api_key=api_key, timeout=timeout)
        self._client = client
        self.country = (country or "").strip().lower() or None
        self.retries = max(0, int(retries))
        self.backoff = float(backoff)
        self.max_backoff = float(max_backoff)
        self.on_retry = on_retry
        transient = tuple(transient_errors) if transient_errors is not None else _transient_errors()
        self._transient = (*transient, FiverrParseError)
        self._sleep = sleep

    # ------------------------------------------------------------------ #
    # Fetching
    # ------------------------------------------------------------------ #

    def _retry(self, action: Callable[[], T]) -> T:
        """Run ``action``, retrying transient failures with doubling backoff."""
        attempt = 0
        while True:
            try:
                return action()
            except Exception as exc:
                if not isinstance(exc, self._transient) or attempt >= self.retries:
                    raise
                attempt += 1
                delay = min(self.backoff * 2 ** (attempt - 1), self.max_backoff)
                if self.on_retry is not None:
                    self.on_retry(attempt, delay, exc)
                self._sleep(delay)

    def fetch(self, url: str) -> str:
        """One getPageSource call: the rendered HTML of a Fiverr page."""
        options: dict[str, Any] = {}
        if self.country:
            options["proxy_country"] = self.country
        try:
            html = self._client.get_page_source(url, **options)
        except Exception as exc:
            if _is_not_found(exc):
                raise FiverrNotFoundError(f"Fiverr has no page at {url}") from exc
            raise
        return html if isinstance(html, str) else ""

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search_page(
        self,
        query: str | None = None,
        *,
        url: str | None = None,
        page: int = 1,
        sort: str | None = None,
        check_filters: bool = True,
        **filters: Any,
    ) -> SearchPage:
        """Fetch one page of a search or category listing (48 slots).

        Args:
            query: Search words, e.g. ``"logo design"``.
            url: A Fiverr search or category URL instead of ``query``.
            page: 1-based page number.
            sort: ``relevance`` (default), ``best_selling`` or ``newest``.
            check_filters: Raise :class:`FiverrFilterError` if the page shows
                that the sort or a filter was not applied.
            **filters: ``seller_level``, ``seller_country``, ``seller_language``,
                ``delivery_days``, ``min_price``, ``max_price``, ``pro``,
                ``online``, ``agency``, ``hourly`` and ``facets``; see
                :func:`fiverr_scraper.urls.build_ref`.
        """
        target = listing_page_url(query, url=url, page=page, sort=sort, **filters)
        result = self._retry(lambda: parse_search_page(self.fetch(target), target))
        if check_filters:
            check_applied(result, sort, **filters)
        return result

    def iter_search(
        self,
        query: str | None = None,
        *,
        url: str | None = None,
        pages: int = 1,
        limit: int | None = None,
        sort: str | None = None,
        seen: set[int] | None = None,
        skip_sponsored: bool = False,
        min_rating: float | None = None,
        min_reviews: int | None = None,
        check_filters: bool = True,
        on_page: Callable[[SearchPage], None] | None = None,
        **filters: Any,
    ) -> Iterator[Gig]:
        """Yield gigs page by page; see :meth:`search` for the arguments."""
        if pages < 1:
            raise ValueError("pages must be at least 1")
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")
        seen = set() if seen is None else seen
        label = " ".join(query.split()) if query else url
        yielded = 0
        for number in range(1, pages + 1):
            result = self.search_page(
                query, url=url, page=number, sort=sort, check_filters=check_filters, **filters
            )
            if on_page is not None:
                on_page(result)
            fresh_organic = 0
            for gig in result.gigs:
                if gig.gig_id in seen:
                    continue
                if not gig.sponsored:
                    fresh_organic += 1
                if skip_sponsored and gig.sponsored:
                    continue
                seen.add(gig.gig_id)
                if min_rating is not None and (gig.rating or 0) < min_rating:
                    continue
                if min_reviews is not None and (gig.reviews or 0) < min_reviews:
                    continue
                gig.query = label
                yield gig
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            # Past the last page Fiverr keeps serving its sponsored slots only.
            if not result.has_more or fresh_organic == 0:
                return

    def search(
        self,
        query: str | None = None,
        *,
        url: str | None = None,
        pages: int = 1,
        limit: int | None = None,
        sort: str | None = None,
        seen: set[int] | None = None,
        skip_sponsored: bool = False,
        min_rating: float | None = None,
        min_reviews: int | None = None,
        check_filters: bool = True,
        on_page: Callable[[SearchPage], None] | None = None,
        **filters: Any,
    ) -> list[Gig]:
        """Search Fiverr gigs (or read a category) and collect them across pages.

        Args:
            query: Search words, e.g. ``"wordpress website"``.
            url: A Fiverr search or category URL copied from the browser.
            pages: Pages to fetch. Stops early at the last page.
            limit: Return at most this many gigs.
            sort: ``relevance`` (default), ``best_selling`` or ``newest``.
            seen: Shared set of gig IDs; gigs already in it are skipped. Pass
                the same set to several calls to de-duplicate across searches.
            skip_sponsored: Drop gigs shown only in sponsored slots.
            min_rating: Keep gigs rated at least this (gigs without reviews are dropped).
            min_reviews: Keep gigs with at least this many reviews.
            check_filters: Raise :class:`FiverrFilterError` when a requested
                sort or filter was not applied.
            on_page: Callback invoked with every fetched :class:`SearchPage`.
            **filters: ``seller_level``, ``seller_country``, ``seller_language``,
                ``delivery_days``, ``min_price``, ``max_price``, ``pro``,
                ``online``, ``agency``, ``hourly``, ``facets``; see
                :func:`fiverr_scraper.urls.build_ref`.
        """
        return list(
            self.iter_search(
                query,
                url=url,
                pages=pages,
                limit=limit,
                sort=sort,
                seen=seen,
                skip_sponsored=skip_sponsored,
                min_rating=min_rating,
                min_reviews=min_reviews,
                check_filters=check_filters,
                on_page=on_page,
                **filters,
            )
        )

    def search_many(
        self,
        queries: Iterable[str],
        *,
        on_query: Callable[[str, list[Gig]], None] | None = None,
        **options: Any,
    ) -> list[Gig]:
        """Run :meth:`search` for several queries, merged and de-duplicated by gig ID."""
        seen: set[int] = options.pop("seen", None) or set()
        results: list[Gig] = []
        for query in queries:
            found = self.search(query, seen=seen, **options)
            if on_query is not None:
                on_query(query, found)
            results.extend(found)
        return results

    def filters(self, query: str | None = None, *, url: str | None = None) -> SearchPage:
        """First page of a listing (one request), for its ``filters``: every
        sidebar filter Fiverr offers there with its values and gig counts."""
        return self.search_page(query, url=url, check_filters=False)

    # ------------------------------------------------------------------ #
    # Gig pages and seller profiles
    # ------------------------------------------------------------------ #

    def gig(self, gig: str | Gig) -> GigDetails:
        """Read a gig page: packages with prices and delivery times, description,
        FAQ, tags, rating breakdown, latest reviews and the seller.

        Args:
            gig: A gig URL, a ``seller/gig-slug`` path or a :class:`Gig` from a search.

        Raises:
            FiverrNotFoundError: no such gig.
        """
        target = gig_url(gig.url if isinstance(gig, Gig) else gig)
        return self._retry(lambda: parse_gig_page(self.fetch(target), target))

    def gigs(
        self,
        items: Iterable[str | Gig],
        *,
        on_error: Callable[[str, Exception], None] | None = None,
    ) -> list[GigDetails]:
        """Read several gig pages; failures go to ``on_error`` (or are raised)."""
        found: list[GigDetails] = []
        for item in items:
            try:
                found.append(self.gig(item))
            except Exception as exc:
                if on_error is None:
                    raise
                on_error(item.url if isinstance(item, Gig) else str(item), exc)
        return found

    def seller(self, seller: str) -> SellerProfile:
        """Read a seller's profile: level, rating, languages, skills, education,
        certifications, their gigs and latest reviews.

        Args:
            seller: A username (``"someseller"``), profile URL or gig URL.

        Raises:
            FiverrNotFoundError: no such seller.
        """
        target = seller_url(seller)
        return self._retry(lambda: parse_seller_page(self.fetch(target), target))


__all__ = [
    "FILTERS",
    "SORTS",
    "FiverrScraper",
    "check_applied",
    "listing_page_url",
]
