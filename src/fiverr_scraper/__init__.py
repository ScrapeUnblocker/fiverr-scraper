"""Scrape Fiverr gigs, gig pages and seller profiles with the ScrapeUnblocker API.

Search Fiverr (or read any category listing) with Fiverr's own sort orders and
filters - seller level, seller country and language, delivery time, budget,
Pro, online now, agency, hourly and every category-specific filter - and get
every gig card as a typed record: gig ID, title, starting price in USD,
delivery days, rating and review count, seller name, country, level, rating
and languages, Pro / Fiverr's Choice / sponsored flags, attributes, images and
URL. Gig pages add every package (price, delivery time, revisions, included
features, extra-fast add-on), description, FAQ, tags, star breakdown, latest
reviews and the seller's stats; seller profiles add skills, education,
certifications and all of the seller's gigs. Pages are fetched through the
ScrapeUnblocker ``getPageSource`` API.

    >>> from fiverr_scraper import FiverrScraper
    >>> fiverr = FiverrScraper()                       # reads SCRAPEUNBLOCKER_KEY
    >>> gigs = fiverr.search("logo design", seller_level=["top_rated"], delivery_days=3)
    >>> gigs[0].title, gigs[0].price, gigs[0].seller_level
    >>> fiverr.gig(gigs[0]).packages
"""

from .export import (
    PACKAGE_COLUMNS,
    csv_string,
    flatten,
    package_rows,
    packages_to_csv,
    to_json,
    to_jsonl,
    write_csv,
)
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
from .parsing import (
    FiverrError,
    FiverrFilterError,
    FiverrNotFoundError,
    FiverrParseError,
    extract_props,
    parse_gig_page,
    parse_search_page,
    parse_seller_page,
)
from .scraper import FILTERS, FiverrScraper, check_applied, listing_page_url
from .urls import (
    DELIVERY_DAYS,
    PAGE_SIZE,
    SELLER_LEVELS,
    SORTS,
    build_ref,
    gig_url,
    search_url,
    seller_url,
)

__version__ = "0.1.0"

__all__ = [
    "DELIVERY_DAYS",
    "FILTERS",
    "PACKAGE_COLUMNS",
    "PAGE_SIZE",
    "SELLER_LEVELS",
    "SORTS",
    "FilterGroup",
    "FilterOption",
    "FiverrError",
    "FiverrFilterError",
    "FiverrNotFoundError",
    "FiverrParseError",
    "FiverrScraper",
    "Gig",
    "GigDetails",
    "Package",
    "Review",
    "SearchPage",
    "Seller",
    "SellerProfile",
    "__version__",
    "build_ref",
    "check_applied",
    "csv_string",
    "extract_props",
    "flatten",
    "gig_url",
    "listing_page_url",
    "package_rows",
    "packages_to_csv",
    "parse_gig_page",
    "parse_search_page",
    "parse_seller_page",
    "search_url",
    "seller_url",
    "to_json",
    "to_jsonl",
    "write_csv",
]
