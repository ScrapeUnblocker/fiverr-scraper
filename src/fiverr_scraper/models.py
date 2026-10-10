"""Typed records returned by the scraper. Every record has ``to_dict()``."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


class _Record:
    def to_dict(self) -> dict[str, Any]:
        return {key: _plain(value) for key, value in asdict(self).items()}  # type: ignore[call-overload]


@dataclass
class Gig(_Record):
    """One gig card of a search, category or seller listing. Prices are in USD."""

    gig_id: int
    title: str
    url: str
    price: float | None = None
    currency: str = "USD"
    delivery_days: int | None = None
    packages: int | None = None
    hourly_rate: float | None = None
    rating: float | None = None
    reviews: int | None = None
    seller_username: str | None = None
    seller_name: str | None = None
    seller_id: int | None = None
    seller_country: str | None = None
    seller_level: str | None = None
    seller_rating: float | None = None
    seller_reviews: int | None = None
    seller_online: bool | None = None
    seller_languages: list[str] = field(default_factory=list)
    seller_url: str | None = None
    seller_image: str | None = None
    agency: str | None = None
    pro: bool = False
    fiverr_choice: bool = False
    sponsored: bool = False
    offers_consultation: bool = False
    offers_subscription: bool = False
    subscription_discount: int | None = None
    category_id: int | None = None
    sub_category_id: int | None = None
    nested_sub_category_id: int | None = None
    attributes: dict[str, list[str]] = field(default_factory=dict)
    image: str | None = None
    images: list[str] = field(default_factory=list)
    video: str | None = None
    slug: str | None = None
    position: int | None = None
    page: int | None = None
    query: str | None = None


@dataclass
class FilterOption(_Record):
    value: str
    label: str | None = None
    count: int | None = None
    selected: bool = False


@dataclass
class FilterGroup(_Record):
    """A sidebar filter of a listing. Pass ``key=value`` (``value`` of an option)
    as a facet filter to apply it."""

    key: str
    label: str | None = None
    kind: str | None = None
    multi: bool = False
    options: list[FilterOption] = field(default_factory=list)

    @property
    def values(self) -> list[str]:
        return [option.value for option in self.options]


@dataclass
class SearchPage(_Record):
    """One page of a Fiverr search or category listing."""

    url: str
    page: int = 1
    query: str | None = None
    flow: str | None = None
    sort: str | None = None
    total: int | None = None
    has_more: bool = False
    page_size: int | None = None
    category: str | None = None
    sub_category: str | None = None
    sub_category_id: int | None = None
    currency: str = "USD"
    active_filters: dict[str, Any] = field(default_factory=dict)
    gigs: list[Gig] = field(default_factory=list)
    filters: list[FilterGroup] = field(default_factory=list)

    @property
    def organic(self) -> list[Gig]:
        """The gigs that are not in a sponsored slot."""
        return [gig for gig in self.gigs if not gig.sponsored]

    def filter_group(self, key: str) -> FilterGroup | None:
        return next((group for group in self.filters if group.key == key), None)


@dataclass
class Package(_Record):
    """A gig package (Basic / Standard / Premium). Prices are in USD."""

    tier: str
    name: str | None = None
    description: str | None = None
    price: float | None = None
    delivery_days: float | None = None
    revisions: int | str | None = None
    features: list[str] = field(default_factory=list)
    extra_fast_price: float | None = None
    extra_fast_days: float | None = None


@dataclass
class Review(_Record):
    review_id: str | None = None
    rating: float | None = None
    comment: str | None = None
    reviewer: str | None = None
    reviewer_country: str | None = None
    reviewer_country_code: str | None = None
    created_at: str | None = None
    order_price_range: str | None = None
    order_duration_days: int | None = None
    repeat_buyer: bool | None = None
    business: bool | None = None
    seller_response: str | None = None
    work_sample: str | None = None
    gig_id: int | None = None


@dataclass
class Seller(_Record):
    """The seller block of a gig page."""

    username: str | None = None
    name: str | None = None
    seller_id: int | None = None
    url: str | None = None
    country_code: str | None = None
    level: str | None = None
    rating: float | None = None
    reviews: int | None = None
    member_since: str | None = None
    response_hours: int | None = None
    completed_orders: int | None = None
    last_delivery: str | None = None
    languages: list[dict[str, str | None]] = field(default_factory=list)
    one_liner: str | None = None
    description: str | None = None
    pro: bool = False
    verified: bool | None = None
    highly_responsive: bool | None = None
    on_vacation: bool | None = None
    image: str | None = None


@dataclass
class GigDetails(_Record):
    """Everything a gig page shows: packages, description, FAQ, reviews and seller."""

    gig_id: int
    title: str
    url: str
    currency: str = "USD"
    price_min: float | None = None
    price_max: float | None = None
    rating: float | None = None
    reviews_count: int | None = None
    star_counts: dict[str, int] = field(default_factory=dict)
    rating_breakdown: dict[str, float | None] = field(default_factory=dict)
    orders_in_queue: int | None = None
    favorites: int | None = None
    category: str | None = None
    category_slug: str | None = None
    sub_category: str | None = None
    sub_category_slug: str | None = None
    nested_sub_category: str | None = None
    pro: bool = False
    packages: list[Package] = field(default_factory=list)
    subscription_discounts: list[dict[str, Any]] = field(default_factory=list)
    consultation: list[dict[str, Any]] = field(default_factory=list)
    description: str | None = None
    attributes: dict[str, list[str]] = field(default_factory=dict)
    faq: list[dict[str, str]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    ai_summary: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    seller: Seller = field(default_factory=Seller)
    other_gig_ids: list[int] = field(default_factory=list)

    def package(self, tier: str) -> Package | None:
        """The ``basic``, ``standard`` or ``premium`` package, if the gig has it."""
        return next((p for p in self.packages if p.tier == tier.lower()), None)


@dataclass
class SellerProfile(_Record):
    """A seller's public profile with their gigs and latest reviews."""

    username: str
    url: str
    name: str | None = None
    seller_id: int | None = None
    country_code: str | None = None
    country: str | None = None
    timezone: str | None = None
    member_since: str | None = None
    level: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    star_counts: dict[str, int] = field(default_factory=dict)
    rating_breakdown: dict[str, float | None] = field(default_factory=dict)
    response_hours: int | None = None
    one_liner: str | None = None
    description: str | None = None
    pro: bool = False
    verified: bool | None = None
    highly_responsive: bool | None = None
    on_vacation: bool | None = None
    agency: str | None = None
    image: str | None = None
    languages: list[dict[str, str | None]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    certifications: list[dict[str, Any]] = field(default_factory=list)
    gigs_count: int | None = None
    gigs: list[Gig] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
