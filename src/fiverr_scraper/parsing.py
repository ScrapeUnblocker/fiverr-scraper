"""Turn Fiverr pages into typed records.

Every Fiverr page this package reads (search and category listings, gig pages,
seller profiles) embeds the data it renders as one JSON document in a
``<script id="perseus-initial-props">`` tag. The parsers below read that
document, so no HTML layout or CSS selector is involved. Fiverr stores package
prices in cents and package delivery times in hours; both are converted to
dollars and days here.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

from .models import (
    FilterGroup,
    FilterOption,
    Gig,
    GigDetails,
    Package,
    Review,
    SearchPage,
    Seller,
    SellerProfile,
)
from .urls import absolute, seller_url, sort_name


class FiverrError(Exception):
    """Base class for errors raised by this package."""


class FiverrParseError(FiverrError):
    """The page did not carry the data expected (blocked, half-loaded or changed)."""


class FiverrNotFoundError(FiverrError):
    """Fiverr has no such gig or seller."""


class FiverrFilterError(FiverrError):
    """Fiverr did not apply a requested sort order or filter."""


_PROPS_RE = re.compile(
    r"<script[^>]*\bid=[\"']perseus-initial-props[\"'][^>]*>(.*?)</script>", re.S | re.I
)

#: Package tiers by Fiverr package id.
TIERS = {1: "basic", 2: "standard", 3: "premium"}

#: Fiverr's language proficiency levels (search cards use the numbers).
LANGUAGE_LEVELS = {1: "basic", 2: "conversational", 3: "fluent", 4: "native_or_bilingual"}

_MEDIA_SKIP = (".pdf", ".mp4", ".mov", ".mp3", ".wav")


def extract_props(html: str) -> dict[str, Any]:
    """The JSON document a Fiverr page embeds for its own rendering."""
    match = _PROPS_RE.search(html or "")
    if not match:
        raise FiverrParseError("no Fiverr page data found (not a Fiverr page, or not loaded)")
    try:
        data = json.loads(match.group(1))
    except ValueError as exc:
        raise FiverrParseError(f"unreadable Fiverr page data: {exc}") from exc
    if not isinstance(data, dict):
        raise FiverrParseError("unexpected Fiverr page data")
    return data


# ---------------------------------------------------------------------- #
# Small value helpers
# ---------------------------------------------------------------------- #


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    return text or None


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float(value: Any, digits: int = 2) -> float | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def _whole(number: float | None) -> float | int | None:
    if number is None:
        return None
    return int(number) if float(number).is_integer() else number


def cents(value: Any) -> float | None:
    """A Fiverr price in cents as dollars (``2500`` -> ``25.0``)."""
    number = _float(value, 4)
    return None if number is None else round(number / 100, 2)


def hours_to_days(value: Any) -> float | None:
    """A Fiverr duration in hours as days (``72`` -> ``3``; ``36`` -> ``1.5``)."""
    number = _float(value, 4)
    if number is None or number <= 0:
        return None
    return _whole(round(number / 24, 2))


def epoch_date(seconds: Any) -> str | None:
    """Unix seconds as an ISO date."""
    number = _float(seconds, 3)
    if not number:
        return None
    return datetime.fromtimestamp(number, tz=timezone.utc).date().isoformat()


def epoch_ms_iso(millis: Any) -> str | None:
    """Unix milliseconds as an ISO-8601 UTC timestamp."""
    number = _float(millis, 3)
    if not number:
        return None
    moment = datetime.fromtimestamp(number / 1000, tz=timezone.utc).replace(microsecond=0)
    return moment.isoformat().replace("+00:00", "Z")


def normalize_level(value: Any) -> str | None:
    """A seller level from any Fiverr spelling as ``top_rated_seller``,
    ``level_two_seller``, ``level_one_seller`` or ``new_seller``."""
    if value is None:
        return None
    key = str(value).strip().lower()
    if key in ("", "na", "no_level", "new", "new_seller", "level_zero", "level_0"):
        return "new_seller"
    if "trs" in key or "top_rated" in key:
        return "top_rated_seller"
    if "two" in key or key.endswith("2"):
        return "level_two_seller"
    if "one" in key or key.endswith("1"):
        return "level_one_seller"
    return key


def language_level(value: Any) -> str | None:
    """A language proficiency (``3`` or ``"FLUENT"``) as ``fluent``, ``native_or_bilingual``, ..."""
    if value is None:
        return None
    number = _int(value)
    if number is not None and not isinstance(value, str):
        return LANGUAGE_LEVELS.get(number, str(number))
    if isinstance(value, str) and value.strip().isdigit():
        return LANGUAGE_LEVELS.get(int(value), value.strip())
    text = _str(value)
    return text.lower() if text else None


def _languages(entries: Iterable[Any]) -> list[dict[str, str | None]]:
    found = []
    for entry in entries:
        entry = _dict(entry)
        code = _str(entry.get("code") or entry.get("name"))
        if code:
            found.append({"code": code.lower(), "level": language_level(entry.get("level"))})
    return found


class _TextExtractor(HTMLParser):
    _BLOCKS = {"p", "div", "br", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in self._BLOCKS:
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: Any) -> str | None:
    """Gig description HTML as plain text with paragraph and list breaks kept."""
    if not html or not isinstance(html, str):
        return None
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


# ---------------------------------------------------------------------- #
# Listings
# ---------------------------------------------------------------------- #


def parse_gig_card(
    item: dict[str, Any],
    *,
    page: int | None = None,
    query: str | None = None,
    position: int | None = None,
) -> Gig | None:
    """One gig card of a listing (search, category or seller page)."""
    item = _dict(item)
    gig_id = _int(item.get("gig_id") or item.get("gigId"))
    title = _str(item.get("title"))
    if gig_id is None or not title:
        return None
    username = _str(item.get("seller_name"))
    slug = _str(item.get("cached_slug"))
    path = _str(item.get("gig_url")) or (f"/{username}/{slug}" if username and slug else None)
    kind = _str(item.get("type")) or ""
    recommended = _dict(_dict(item.get("packages")).get("recommended"))
    price = _float(item.get("price_i"))
    if price is None:
        price = _float(recommended.get("price"))
    seller_rating = _dict(item.get("seller_rating"))
    discounts = [
        _int(_dict(option).get("discount_percentage"))
        for option in _list(item.get("recurring_options"))
    ]
    discounts = [value for value in discounts if value]
    attributes: dict[str, list[str]] = {}
    for entry in _list(item.get("metadata")):
        entry = _dict(entry)
        key = _str(entry.get("type"))
        values = entry.get("value")
        values = values if isinstance(values, list) else [values]
        cleaned = [str(value) for value in values if value not in (None, "")]
        if key and cleaned:
            attributes[key] = cleaned
    images = [
        image
        for image in (
            _str(_dict(asset).get("cloud_img_main_gig")) for asset in _list(item.get("assets"))
        )
        if image
    ]
    videos = [_str(_dict(entry).get("stream_url")) for entry in _list(item.get("attachments"))]
    agency = _dict(item.get("agency"))
    username_url = absolute(_str(item.get("seller_url"))) or (
        seller_url(username) if username else None
    )
    return Gig(
        gig_id=gig_id,
        title=title,
        url=absolute(path) or "",
        price=price,
        delivery_days=_int(recommended.get("duration")),
        packages=_int(item.get("num_of_packages")),
        hourly_rate=cents(item.get("hourly_rate")),
        rating=_float(item.get("buying_review_rating")),
        reviews=_int(item.get("buying_review_rating_count")),
        seller_username=username,
        seller_name=_str(item.get("seller_display_name")),
        seller_id=_int(item.get("seller_id") or item.get("sellerId")),
        seller_country=_str(item.get("seller_country")),
        seller_level=normalize_level(item.get("seller_level")) if "seller_level" in item else None,
        seller_rating=_float(seller_rating.get("score")),
        seller_reviews=_int(seller_rating.get("count")),
        seller_online=_bool(item.get("seller_online")),
        seller_languages=[lang["code"] for lang in _languages(_list(item.get("seller_languages")))],
        seller_url=username_url,
        seller_image=_str(item.get("seller_img")),
        agency=_str(agency.get("slug") or agency.get("name")),
        pro=bool(item.get("is_pro")) or kind == "pro",
        fiverr_choice=bool(item.get("is_fiverr_choice")) or kind == "fiverr_choice",
        sponsored=kind == "promoted_gigs",
        offers_consultation=bool(item.get("offer_consultation")),
        offers_subscription=bool(item.get("has_recurring_option")) or bool(discounts),
        subscription_discount=max(discounts) if discounts else None,
        category_id=_int(item.get("category_id")),
        sub_category_id=_int(item.get("sub_category_id")),
        nested_sub_category_id=_int(item.get("nested_sub_category_id")) or None,
        attributes=attributes,
        image=images[0] if images else None,
        images=images,
        video=next((video for video in videos if video), None),
        slug=slug,
        position=position,
        page=page,
        query=query,
    )


def parse_gig_cards(
    items: Iterable[Any], *, page: int | None = None, query: str | None = None
) -> list[Gig]:
    """Gig cards in page order, one per gig.

    Fiverr repeats some gigs of a page in sponsored slots. A gig that also ranks
    organically keeps its organic card (``sponsored=False``) and position.
    """
    by_id: dict[int, Gig] = {}
    for index, item in enumerate(items):
        gig = parse_gig_card(item, page=page, query=query, position=index + 1)
        if gig is None:
            continue
        known = by_id.get(gig.gig_id)
        if known is None or (known.sponsored and not gig.sponsored):
            by_id[gig.gig_id] = gig
    return sorted(by_id.values(), key=lambda gig: gig.position or 0)


def _filter_groups(props: dict[str, Any]) -> list[FilterGroup]:
    groups = []
    for entry in _list(_dict(props.get("appFilters")).get("filters")):
        entry = _dict(entry)
        key = _str(entry.get("id"))
        if not key:
            continue
        options = []
        for option in _list(entry.get("options")):
            option = _dict(option)
            value = _str(option.get("id"))
            if value is None or key == "gig_price_range":
                continue
            label = _str(option.get("alias"))
            if key == "pro":
                value, label = "any", label or "Pro services"
            options.append(
                FilterOption(
                    value=value,
                    label=label,
                    count=_int(option.get("count")),
                    selected=bool(option.get("selected")),
                )
            )
        groups.append(
            FilterGroup(
                key=key,
                label=_str(entry.get("alias")) or ("Budget" if key == "price_buckets" else None),
                kind=_str(entry.get("display_type")),
                multi=entry.get("selector") == "multi",
                options=options,
            )
        )
    return groups


def parse_search_page(html: str, url: str) -> SearchPage:
    """One page of a Fiverr search or category listing."""
    props = extract_props(html)
    items = props.get("items")
    if not isinstance(items, list):
        raise FiverrParseError(f"the page is not a Fiverr gig listing ({url})")
    app = _dict(props.get("appData"))
    pagination = _dict(app.get("pagination"))
    raw = _dict(props.get("rawListingData"))
    page = _int(pagination.get("page")) or 1
    query = _str(props.get("listingQuery"))
    sub = _dict(props.get("subCategoryData"))
    display = _dict(props.get("displayData"))
    has_more = raw.get("has_more")
    return SearchPage(
        url=url,
        page=page,
        query=query,
        flow=_str(props.get("flow")),
        sort=sort_name(_str(_dict(app.get("sorting")).get("sortBy"))),
        total=_int(raw.get("num_found"))
        if raw.get("num_found") is not None
        else _int(pagination.get("total")),
        has_more=bool(has_more) if has_more is not None else bool(items),
        page_size=_int(pagination.get("page_size")),
        category=_str(display.get("categoryName")) or _str(_dict(sub.get("category")).get("name")),
        sub_category=_str(sub.get("name")) or _str(display.get("subCategoryName")),
        sub_category_id=_int(sub.get("id")),
        # Fiverr's raw prices are USD whatever currency a visitor's country displays.
        currency="USD",
        active_filters=_dict(props.get("activeFilters")),
        gigs=parse_gig_cards(items, page=page, query=query),
        filters=_filter_groups(props),
    )


# ---------------------------------------------------------------------- #
# Gig pages
# ---------------------------------------------------------------------- #


def _review(entry: Any) -> Review:
    entry = _dict(entry)
    response = _dict(entry.get("seller_response"))
    return Review(
        review_id=_str(entry.get("id")),
        rating=_float(entry.get("value")),
        comment=_str(entry.get("comment")),
        reviewer=_str(entry.get("username")),
        reviewer_country=_str(entry.get("reviewer_country")),
        reviewer_country_code=_str(entry.get("reviewer_country_code")),
        created_at=_str(entry.get("created_at")),
        order_price_range=_str(
            entry.get("order_price_range_usd") or entry.get("order_price_range")
        ),
        order_duration_days=_int(entry.get("order_duration_in_days")),
        repeat_buyer=_bool(entry.get("repeat_buyer")),
        business=_bool(entry.get("is_business")),
        seller_response=_str(response.get("comment")),
        work_sample=_str(entry.get("work_sample")),
        gig_id=_int(entry.get("gig_id")),
    )


def _star_counts(breakdown: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in _list(breakdown):
        entry = _dict(entry)
        stars = _int(entry.get("average_valuation_value") or entry.get("value"))
        count = _int(entry.get("count"))
        if stars is not None and count is not None:
            counts[str(stars)] = count
    return dict(sorted(counts.items(), reverse=True))


def _rating_breakdown(summary: Any) -> dict[str, float | None]:
    summary = _dict(summary)
    names = {
        "communication": "communication_valuation",
        "quality": "quality_of_delivery_valuation",
        "value": "value_for_money_valuation",
    }
    found = {name: _float(summary.get(key)) for name, key in names.items()}
    return {name: value for name, value in found.items() if value is not None}


def _revisions(entry: Any) -> int | str | None:
    entry = _dict(entry)
    if not entry:
        return None
    if not entry.get("included"):
        return 0
    value = _int(entry.get("value"))
    if value is not None and value < 0:
        return "unlimited"
    return value


def _features(entries: Iterable[Any]) -> list[str]:
    found = []
    for entry in entries:
        entry = _dict(entry)
        label = _str(entry.get("label")) or _str(entry.get("name"))
        if not label or not entry.get("included"):
            continue
        value = _int(entry.get("value"))
        if entry.get("type") == "NUMERIC" and value:
            found.append(f"{label}: {'unlimited' if value < 0 else value}")
        else:
            found.append(label)
    return found


def _package(entry: Any) -> Package | None:
    entry = _dict(entry)
    if not entry:
        return None
    pid = _int(entry.get("id"))
    fast = _dict(entry.get("extraFast"))
    fast_price = cents(fast.get("price")) if fast else None
    return Package(
        tier=TIERS.get(pid or 0, f"package_{pid}"),
        name=_str(entry.get("title")),
        description=_str(entry.get("description")),
        price=cents(entry.get("price")),
        delivery_days=hours_to_days(entry.get("duration")),
        revisions=_revisions(entry.get("revisions")),
        features=_features(_list(entry.get("features"))),
        extra_fast_price=fast_price or None,
        extra_fast_days=hours_to_days(fast.get("duration")) if fast_price else None,
    )


def _gallery(slides: Iterable[Any]) -> list[str]:
    found = []
    for slide in slides:
        src = _str(_dict(_dict(slide).get("slide")).get("src"))
        if (
            src
            and "/video/" not in src
            and not src.lower().endswith(_MEDIA_SKIP)
            and src not in found
        ):
            found.append(src)
    return found


def _attributes(entries: Iterable[Any]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for entry in entries:
        entry = _dict(entry)
        meta = _dict(entry.get("metadata"))
        name = _str(meta.get("alias")) or _str(entry.get("name"))
        values = [
            _str(_dict(option).get("label")) or _str(_dict(option).get("value"))
            for option in _list(entry.get("options"))
        ]
        values = [value for value in values if value]
        if name and values:
            found[name] = values
    return found


def _gig_seller(props: dict[str, Any]) -> Seller:
    seller = _dict(props.get("seller"))
    user = _dict(seller.get("user"))
    card = _dict(props.get("sellerCard"))
    seo = _dict(_dict(props.get("seo")).get("description"))
    username = _str(user.get("name")) or _str(_dict(props.get("outOfOffice")).get("username"))
    image = _dict(_dict(user.get("profileImage")).get("previewUrl")).get("url")
    languages = _languages(_list(user.get("languages"))) or _languages(
        _list(card.get("proficientLanguages"))
    )
    rating = _dict(seller.get("rating"))
    return Seller(
        username=username,
        name=_str(_dict(user.get("profile")).get("displayName")),
        seller_id=_int(seller.get("id") or user.get("id")),
        url=seller_url(username) if username else None,
        country_code=_str(_dict(user.get("address")).get("countryCode"))
        or _str(card.get("countryCode")),
        level=normalize_level(seo.get("sellerAchievement") or seller.get("sellerLevel")),
        rating=_float(rating.get("score")) or _float(card.get("rating")),
        reviews=_int(rating.get("count")) or _int(card.get("ratingsCount")),
        member_since=epoch_date(user.get("joinedAt") or card.get("memberSince")),
        response_hours=_int(_dict(seller.get("responseTime")).get("inHours"))
        or _int(card.get("responseTime")),
        completed_orders=_int(seller.get("completedOrdersCount")),
        last_delivery=epoch_ms_iso(card.get("recentDelivery")),
        languages=languages,
        one_liner=_str(seller.get("oneLinerTitle")) or _str(card.get("oneLiner")),
        description=_str(seller.get("description")) or _str(card.get("description")),
        pro=bool(seller.get("isPro") or card.get("isPro")),
        verified=_bool(seller.get("isVerified")),
        highly_responsive=_bool(seller.get("isHighlyResponsive")),
        on_vacation=_bool(seller.get("isOnVacation")),
        image=_str(image) or _str(card.get("profilePhoto")),
    )


def parse_gig_page(html: str, url: str) -> GigDetails:
    """A gig page: packages, description, FAQ, tags, rating, latest reviews and seller.

    Raises:
        FiverrNotFoundError: Fiverr answered with the seller's profile instead
            (it does that for a gig that does not exist or was removed).
    """
    props = extract_props(html)
    general = _dict(props.get("general"))
    gig_id = _int(general.get("gigId"))
    if gig_id is None:
        if "gigsData" in props or "reviewsData" in props:
            raise FiverrNotFoundError(f"no such gig: {url} (Fiverr showed the seller's profile)")
        raise FiverrParseError(f"the page is not a Fiverr gig page ({url})")
    overview = _dict(props.get("overview"))
    overview_gig = _dict(overview.get("gig"))
    categories = _dict(overview.get("categories"))
    reviews = _dict(props.get("reviews"))
    packages_block = _dict(props.get("packages"))
    packages = [p for p in (_package(e) for e in _list(packages_block.get("packageList"))) if p]
    offers = _dict(_dict(_dict(props.get("seo")).get("schemaMarkup")).get("gigOffers"))
    prices = [p.price for p in packages if p.price is not None]
    price_min = min(prices) if prices else _float(offers.get("lowPrice"))
    price_max = max(prices) if prices else _float(offers.get("highPrice"))
    subscriptions = []
    for option in _list(packages_block.get("recurringOptions")):
        option = _dict(option)
        unit = (_str(option.get("durationTimeUnit")) or "").replace("time_unit_", "") or None
        subscriptions.append(
            {
                "duration": _int(option.get("duration")),
                "unit": unit,
                "discount_percent": _int(option.get("discountPercentage")),
            }
        )
    consultation = [
        {"minutes": _int(_dict(p).get("session_minutes")), "price": _float(_dict(p).get("price"))}
        for p in _list(_dict(props.get("consultationData")).get("pricing"))
        if (_str(_dict(p).get("status")) or "ACTIVE").upper() == "ACTIVE"
    ]
    summary = _dict(props.get("aiSummary"))
    seller = _gig_seller(props)
    slug = _str(_dict(props.get("portfolio")).get("slug"))
    canonical = f"{seller.url}/{slug}" if seller.url and slug else url
    return GigDetails(
        gig_id=gig_id,
        title=_str(general.get("gigTitle")) or _str(overview_gig.get("title")) or "",
        url=canonical,
        price_min=price_min,
        price_max=price_max,
        rating=_float(overview_gig.get("rating")) or _float(reviews.get("average_valuation")),
        reviews_count=_int(overview_gig.get("ratingsCount")) or _int(reviews.get("total_count")),
        star_counts=_star_counts(reviews.get("breakdown")),
        rating_breakdown=_rating_breakdown(reviews.get("star_summary")),
        orders_in_queue=_int(overview_gig.get("ordersInQueue")),
        favorites=_int(_dict(props.get("topNav")).get("gigCollectedCount")),
        category=_str(general.get("categoryName")),
        category_slug=_str(general.get("categorySlug")),
        sub_category=_str(general.get("subCategoryName")),
        sub_category_slug=_str(general.get("subCategorySlug")),
        nested_sub_category=_str(_dict(categories.get("nestedSubCategory")).get("name"))
        or _str(general.get("nestedSubCategorySlug")),
        pro=bool(general.get("isPro")),
        packages=packages,
        subscription_discounts=subscriptions,
        consultation=consultation,
        description=html_to_text(_dict(props.get("description")).get("content")),
        attributes=_attributes(_list(_dict(props.get("description")).get("metadataAttributes"))),
        faq=[
            {"question": q, "answer": a}
            for q, a in (
                (_str(_dict(e).get("question")), _str(_dict(e).get("answer")))
                for e in _list(_dict(props.get("faq")).get("questionsAndAnswers"))
            )
            if q
        ],
        tags=[
            tag
            for tag in (
                _str(_dict(e).get("name"))
                for e in _list(_dict(props.get("tags")).get("tagsGigList"))
            )
            if tag
        ],
        ai_summary=[s for s in (_str(x) for x in _list(summary.get("summary"))) if s]
        if summary.get("visible", True)
        else [],
        images=_gallery(_list(_dict(props.get("gallery")).get("slides"))),
        reviews=[_review(entry) for entry in _list(reviews.get("reviews"))],
        seller=seller,
        other_gig_ids=[
            gid
            for gid in (_int(x) for x in _list(_dict(props.get("otherGigs")).get("gigIds")))
            if gid
        ],
    )


# ---------------------------------------------------------------------- #
# Seller profiles
# ---------------------------------------------------------------------- #


def parse_seller_page(html: str, url: str) -> SellerProfile:
    """A seller's public profile with their gigs and latest reviews."""
    props = extract_props(html)
    seller = _dict(props.get("seller"))
    user = _dict(seller.get("user"))
    username = _str(user.get("name"))
    if not username or "general" in props:
        raise FiverrParseError(f"the page is not a Fiverr seller profile ({url})")
    address = _dict(user.get("address"))
    rating = _dict(seller.get("rating"))
    buying = _dict(_dict(props.get("reviewsData")).get("buying_reviews"))
    agency = seller.get("agency")
    agency_name = (
        _str(_dict(agency).get("slug") or _dict(agency).get("name"))
        if isinstance(agency, dict)
        else _str(agency)
    )
    return SellerProfile(
        username=username,
        url=seller_url(username),
        name=_str(_dict(user.get("profile")).get("displayName")),
        seller_id=_int(user.get("id")),
        country_code=_str(address.get("countryCode")),
        country=_str(address.get("countryName")),
        timezone=_str(_dict(user.get("localization")).get("timezone"))
        or _str(_dict(props.get("localizationData")).get("timezone")),
        member_since=epoch_date(user.get("joinedAt")),
        level=normalize_level(seller.get("achievementLevel") or seller.get("sellerLevel")),
        rating=_float(rating.get("score")),
        reviews_count=_int(rating.get("count")) or _int(buying.get("total_count")),
        star_counts=_star_counts(buying.get("breakdown")),
        rating_breakdown=_rating_breakdown(buying.get("star_summary")),
        response_hours=_int(_dict(seller.get("responseTime")).get("inHours")),
        one_liner=_str(seller.get("oneLinerTitle")),
        description=_str(seller.get("description")),
        pro=bool(seller.get("isPro")),
        verified=_bool(seller.get("isVerified")),
        highly_responsive=_bool(seller.get("isHighlyResponsive")),
        on_vacation=_bool(seller.get("isOnVacation")),
        agency=agency_name,
        image=_str(user.get("profileImageUrl")),
        languages=_languages(_list(user.get("languages"))),
        skills=[
            {"name": _str(s.get("name")), "level": (_str(s.get("level")) or "").lower() or None}
            for s in map(_dict, _list(seller.get("activeStructuredSkills")))
            if _str(s.get("name"))
        ],
        education=[
            {
                "school": _str(e.get("school")),
                "degree": _str(e.get("degreeTitle")),
                "field": _str(e.get("degree")),
                "year": _int(e.get("toYear")),
                "country_code": _str(e.get("countryCode")),
            }
            for e in map(_dict, _list(seller.get("activeEducations")))
        ],
        certifications=[
            {
                "name": _str(c.get("certificationName")),
                "issuer": _str(c.get("receivedFrom")),
                "year": _int(c.get("year")),
            }
            for c in map(_dict, _list(seller.get("certifications")))
        ],
        gigs_count=_int(seller.get("approvedGigsCount")),
        gigs=parse_gig_cards(_list(props.get("gigsData"))),
        reviews=[_review(entry) for entry in _list(buying.get("reviews"))],
    )
