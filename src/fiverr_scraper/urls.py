"""Fiverr URLs: search and category listings, gig pages and seller profiles.

Fiverr encodes the sidebar filters of a listing in a single ``ref`` query
parameter: ``key:value`` pairs joined by ``|``, several values of one key
joined by ``,`` (``ref=seller_level:top_rated_seller,level_two_seller|delivery_time:3``).
The sort order is the ``filter`` parameter and the page number is ``page``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Union
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

BASE_URL = "https://www.fiverr.com"
SEARCH_PATH = "/search/gigs"

#: Gigs per listing page (sponsored slots included).
PAGE_SIZE = 48

#: Sort orders whose effect on the results was verified, mapped to Fiverr's ``filter`` value.
SORTS: dict[str, str] = {
    "relevance": "auto",
    "best_selling": "rating",
    "newest": "new",
}
_SORT_ALIASES = {
    "auto": "relevance",
    "recommended": "relevance",
    "rating": "best_selling",
    "best-selling": "best_selling",
    "bestselling": "best_selling",
    "new": "newest",
}

#: Seller levels accepted by :func:`build_ref`, mapped to Fiverr's filter values.
SELLER_LEVELS: dict[str, str] = {
    "top_rated": "top_rated_seller",
    "level_2": "level_two_seller",
    "level_1": "level_one_seller",
    "new": "na",
}
_LEVEL_ALIASES = {
    "top-rated": "top_rated",
    "top_rated_seller": "top_rated",
    "trs": "top_rated",
    "level2": "level_2",
    "level-2": "level_2",
    "level_two": "level_2",
    "level_two_seller": "level_2",
    "level1": "level_1",
    "level-1": "level_1",
    "level_one": "level_1",
    "level_one_seller": "level_1",
    "na": "new",
    "new_seller": "new",
}

#: Delivery-time choices Fiverr offers (days; 1 = express 24h).
DELIVERY_DAYS = (1, 3, 7)

#: Upper bound Fiverr uses for its own price buckets, used when only a minimum is given.
MAX_PRICE = 50000

FilterValue = Union[str, int, float, bool, Iterable[Any]]


def normalize_sort(sort: str | None) -> str | None:
    """The canonical sort name (``relevance``, ``best_selling``, ``newest``) or ``None``."""
    if sort is None or sort == "":
        return None
    key = str(sort).strip().lower().replace(" ", "_")
    key = _SORT_ALIASES.get(key, key)
    if key not in SORTS:
        raise ValueError(f"unknown sort {sort!r}; choose from: {', '.join(SORTS)}")
    return key


def sort_name(value: str | None) -> str | None:
    """Fiverr's ``filter`` value (``auto``, ``rating``, ...) as a canonical sort name."""
    if not value:
        return None
    for name, fiverr in SORTS.items():
        if fiverr == value:
            return name
    return str(value)


def seller_level_value(level: str) -> str:
    """Fiverr's filter value for a seller level such as ``top_rated`` or ``level_2``."""
    key = str(level).strip().lower().replace(" ", "_")
    key = _LEVEL_ALIASES.get(key, key)
    if key not in SELLER_LEVELS:
        raise ValueError(f"unknown seller level {level!r}; choose from: {', '.join(SELLER_LEVELS)}")
    return SELLER_LEVELS[key]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        items: Iterable[Any] = str(value).split(",")
    else:
        items = value
    return [str(item).strip() for item in items if str(item).strip()]


def parse_facets(facets: Mapping[str, Any] | Iterable[str] | None) -> dict[str, list[str]]:
    """Facet filters as ``{key: [values]}`` from a mapping or ``"key=value"`` strings.

    Repeating a key (``["style=modern", "style=retro"]``) or giving
    comma-separated values (``"style=modern,retro"``) selects several values.
    """
    result: dict[str, list[str]] = {}
    if not facets:
        return result
    pairs: Iterable[tuple[str, Any]]
    if isinstance(facets, Mapping):
        pairs = facets.items()
    else:
        parsed = []
        for item in facets:
            key, sep, value = str(item).partition("=")
            if not sep:
                key, sep, value = str(item).partition(":")
            if not sep or not key.strip():
                raise ValueError(f"facet filters look like key=value, got {item!r}")
            parsed.append((key, value))
        pairs = parsed
    for key, value in pairs:
        values = result.setdefault(str(key).strip(), [])
        for item in _as_list(value):
            if item not in values:
                values.append(item)
    return {key: values for key, values in result.items() if values}


def build_ref(
    *,
    seller_level: str | Iterable[str] | None = None,
    seller_country: str | Iterable[str] | None = None,
    seller_language: str | Iterable[str] | None = None,
    delivery_days: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    pro: bool = False,
    online: bool = False,
    agency: bool = False,
    hourly: bool = False,
    facets: Mapping[str, Any] | Iterable[str] | None = None,
) -> dict[str, list[str]]:
    """Fiverr's ``ref`` filters as ``{key: [values]}`` from friendly arguments.

    Args:
        seller_level: ``top_rated``, ``level_2``, ``level_1`` and/or ``new``.
        seller_country: ISO country codes of the seller's location (``US``, ``GB``, ...).
        seller_language: Language codes the seller speaks (``en``, ``de``, ...).
        delivery_days: Delivered within 1 (express 24h), 3 or 7 days.
        min_price, max_price: Budget range of the gig's starting price, in USD.
        pro: Fiverr Pro (vetted) services only.
        online: Sellers that are online now.
        agency: Agencies only.
        hourly: Gigs that also offer an hourly rate.
        facets: Any other filter of the listing, e.g. ``{"style": "flat_minimalist"}`` or
            ``["service_offerings=subscription"]``; see :meth:`FiverrScraper.filters`.
    """
    ref: dict[str, list[str]] = {}
    levels = [seller_level_value(level) for level in _as_list(seller_level)]
    if levels:
        ref["seller_level"] = levels
    countries = [code.upper() for code in _as_list(seller_country)]
    if countries:
        ref["seller_location"] = countries
    languages = [code.lower() for code in _as_list(seller_language)]
    if languages:
        ref["seller_language"] = languages
    if delivery_days not in (None, ""):
        days = int(delivery_days)  # type: ignore[arg-type]
        if days not in DELIVERY_DAYS:
            raise ValueError(f"delivery_days must be one of {DELIVERY_DAYS}, got {delivery_days}")
        ref["delivery_time"] = [str(days)]
    if min_price is not None or max_price is not None:
        low = 0 if min_price is None else _price(min_price)
        high = MAX_PRICE if max_price is None else _price(max_price)
        if low > high:
            raise ValueError("min_price is higher than max_price")
        ref["gig_price_range"] = [str(low), str(high)]
    if pro:
        ref["pro"] = ["any"]
    if online:
        ref["is_seller_online"] = ["true"]
    if agency:
        ref["is_agency"] = ["true"]
    if hourly:
        ref["has_hourly"] = ["true"]
    for key, values in parse_facets(facets).items():
        if key in ref:
            raise ValueError(f"filter {key!r} given twice")
        ref[key] = values
    return ref


def _price(value: float) -> int:
    number = float(value)
    if number < 0:
        raise ValueError("prices cannot be negative")
    return int(round(number))


def encode_ref(ref: Mapping[str, Iterable[str]]) -> str:
    """``{key: [values]}`` as Fiverr's ``ref`` string (``key:v1,v2|key2:v``)."""
    return "|".join(f"{key}:{','.join(values)}" for key, values in ref.items() if values)


def decode_ref(text: str | None) -> dict[str, list[str]]:
    """Fiverr's ``ref`` string as ``{key: [values]}`` (the inverse of :func:`encode_ref`)."""
    result: dict[str, list[str]] = {}
    for part in (text or "").split("|"):
        key, sep, value = part.partition(":")
        if sep and key.strip():
            result[key.strip()] = _as_list(value)
    return result


def _query_string(params: list[tuple[str, str]]) -> str:
    return urlencode(params, quote_via=quote, safe="")


def is_fiverr_url(url: str | None) -> bool:
    """True for any ``fiverr.com`` URL."""
    if not url:
        return False
    host = urlsplit(str(url).strip()).netloc.lower().split(":")[0]
    return host == "fiverr.com" or host.endswith(".fiverr.com")


def is_listing_url(url: str) -> bool:
    """True for a Fiverr search (``/search/gigs``) or category (``/categories/...``) URL."""
    path = urlsplit(url).path
    return path.startswith(SEARCH_PATH) or path.startswith("/categories/")


def listing_url(
    url: str,
    *,
    page: int = 1,
    sort: str | None = None,
    ref: Mapping[str, Iterable[str]] | None = None,
) -> str:
    """A copied search or category URL with the page, sort and extra filters applied.

    Filters already in the URL are kept; a filter given again replaces the copied one.
    """
    if not is_fiverr_url(url) or not is_listing_url(url):
        raise ValueError(f"not a Fiverr search or category URL: {url!r}")
    if page < 1:
        raise ValueError("page must be at least 1")
    parts = urlsplit(url.strip())
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    merged = {}
    for key, value in params:
        if key == "ref":
            merged.update(decode_ref(value))
    merged.update({key: list(values) for key, values in (ref or {}).items()})
    keep = [(k, v) for k, v in params if k not in ("ref", "page", "filter")]
    canonical = normalize_sort(sort)
    if canonical:
        keep.append(("filter", SORTS[canonical]))
    else:
        keep.extend((k, v) for k, v in params if k == "filter")
    if merged:
        keep.append(("ref", encode_ref(merged)))
    if page > 1:
        keep.append(("page", str(page)))
    return urlunsplit(("https", "www.fiverr.com", parts.path, _query_string(keep), ""))


def search_url(
    query: str,
    *,
    page: int = 1,
    sort: str | None = None,
    ref: Mapping[str, Iterable[str]] | None = None,
) -> str:
    """The Fiverr gig search URL for ``query``, a page, a sort order and ``ref`` filters."""
    words = " ".join(str(query or "").split())
    if not words:
        raise ValueError("give search words or a Fiverr URL")
    if page < 1:
        raise ValueError("page must be at least 1")
    params = [("query", words)]
    canonical = normalize_sort(sort)
    if canonical:
        params.append(("filter", SORTS[canonical]))
    encoded = encode_ref(ref or {})
    if encoded:
        params.append(("ref", encoded))
    if page > 1:
        params.append(("page", str(page)))
    return f"{BASE_URL}{SEARCH_PATH}?{_query_string(params)}"


def _path_parts(text: str) -> list[str]:
    raw = str(text or "").strip()
    if is_fiverr_url(raw):
        raw = urlsplit(raw).path
    elif raw.startswith("http://") or raw.startswith("https://"):
        raise ValueError(f"not a Fiverr URL: {text!r}")
    else:
        raw = raw.split("?", 1)[0].split("#", 1)[0]
    return [part for part in raw.split("/") if part]


def gig_url(gig: str) -> str:
    """The canonical URL of a gig from its URL or ``seller/gig-slug`` path."""
    parts = _path_parts(gig)
    if len(parts) != 2 or parts[0] in ("search", "categories", "gigs"):
        raise ValueError(
            f"a gig looks like https://www.fiverr.com/<seller>/<gig-slug>, got {gig!r}"
        )
    return f"{BASE_URL}/{parts[0]}/{parts[1]}"


def seller_url(seller: str) -> str:
    """The profile URL of a seller from a username, profile URL or gig URL."""
    parts = _path_parts(seller.lstrip("@") if isinstance(seller, str) else seller)
    if not parts or parts[0] in ("search", "categories"):
        raise ValueError(f"not a Fiverr seller: {seller!r}")
    return f"{BASE_URL}/{parts[0]}"


def absolute(path: str | None) -> str | None:
    """A Fiverr path such as ``/seller/gig`` as an absolute URL."""
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return BASE_URL + ("" if path.startswith("/") else "/") + path
