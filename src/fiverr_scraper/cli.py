"""Command-line interface: ``fiverr-scraper <command> ...``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable, TextIO

from . import __version__
from .export import PACKAGE_COLUMNS, csv_string, package_rows, to_json, to_jsonl
from .models import Gig, GigDetails, SearchPage
from .parsing import FiverrError
from .scraper import FiverrScraper, listing_page_url
from .urls import DELIVERY_DAYS, SELLER_LEVELS, SORTS

FORMATS_OUT = ("json", "jsonl", "csv")
OPTIONS_SHOWN = 20

#: Local sort orders for collected gigs.
ORDERS: dict[str, tuple[Callable[[Gig], Any], bool]] = {
    "price": (lambda gig: gig.price, False),
    "price-desc": (lambda gig: gig.price, True),
    "rating": (lambda gig: gig.rating, True),
    "reviews": (lambda gig: gig.reviews, True),
    "delivery": (lambda gig: gig.delivery_days, False),
}


def _stdout() -> TextIO:
    """stdout that always accepts UTF-8 (Windows consoles default to a legacy codepage)."""
    stream = sys.stdout
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # pragma: no cover - exotic streams
            pass
    return stream


def _log(args: argparse.Namespace, message: str) -> None:
    if not getattr(args, "quiet", False):
        print(message, file=sys.stderr, flush=True)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--country",
        default="us",
        metavar="CODE",
        help="Country to route requests through (default: us). Fiverr ranks gigs for the "
        "visitor's country; prices stay in USD",
    )
    parser.add_argument("--retries", type=int, default=3, help="Retries per request (default 3)")
    parser.add_argument("-q", "--quiet", action="store_true", help="No progress on stderr")


def _add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-f", "--format", choices=FORMATS_OUT, default="json")
    parser.add_argument("-o", "--output", help="Write to this file instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")


def _add_listing_filters(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("Fiverr filters (applied by Fiverr)")
    group.add_argument("--sort", choices=list(SORTS), help="Sort order (default: relevance)")
    group.add_argument(
        "--seller-level",
        nargs="+",
        choices=list(SELLER_LEVELS),
        metavar="LEVEL",
        help="Seller levels: " + ", ".join(SELLER_LEVELS),
    )
    group.add_argument(
        "--seller-country",
        nargs="+",
        metavar="CODE",
        help="Seller lives in these countries (ISO codes: US GB DE ...)",
    )
    group.add_argument(
        "--seller-language", nargs="+", metavar="CODE", help="Seller speaks (en de es ...)"
    )
    group.add_argument(
        "--delivery-days",
        type=int,
        choices=DELIVERY_DAYS,
        help="Delivered within 1 (express 24h), 3 or 7 days",
    )
    group.add_argument("--min-price", type=float, metavar="USD", help="Lowest starting price")
    group.add_argument("--max-price", type=float, metavar="USD", help="Highest starting price")
    group.add_argument("--pro", action="store_true", help="Fiverr Pro services only")
    group.add_argument("--online", action="store_true", help="Sellers online now")
    group.add_argument("--agency", action="store_true", help="Agencies only")
    group.add_argument("--hourly", action="store_true", help="Gigs that also offer an hourly rate")
    group.add_argument(
        "--facet",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Any other filter of the listing, e.g. style=flat_minimalist or "
        "service_offerings=subscription (repeatable; see the `filters` command)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fiverr-scraper",
        description="Scrape Fiverr gigs, gig pages and seller profiles via ScrapeUnblocker.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search gigs or read a category listing")
    search.add_argument("queries", nargs="*", metavar="QUERY", help="Search words")
    search.add_argument("--url", help="A Fiverr search or category URL from the browser")
    _add_listing_filters(search)
    local = search.add_argument_group("Local options (applied to the collected gigs)")
    local.add_argument("--skip-sponsored", action="store_true", help="Drop sponsored-only gigs")
    local.add_argument("--min-rating", type=float, metavar="N", help="Minimum gig rating")
    local.add_argument("--min-reviews", type=int, metavar="N", help="Minimum review count")
    local.add_argument("--order", choices=list(ORDERS), help="Sort the collected gigs locally")
    search.add_argument("-p", "--pages", type=int, default=1, help="Pages per query (default 1)")
    search.add_argument("-n", "--limit", type=int, help="At most N gigs per query")
    search.add_argument(
        "--details",
        action="store_true",
        help="Also read every gig page (packages, FAQ, reviews); one extra request per gig",
    )
    search.add_argument(
        "--no-check-filters",
        action="store_true",
        help="Do not fail when Fiverr does not apply a sort or filter",
    )
    search.add_argument(
        "--dry-run", action="store_true", help="Print the first-page URLs; no API calls"
    )
    _add_common(search)
    _add_output(search)

    gig = sub.add_parser("gig", help="Read gig pages (packages, description, FAQ, reviews)")
    gig.add_argument("gigs", nargs="+", metavar="GIG", help="Gig URL or seller/gig-slug path")
    _add_common(gig)
    _add_output(gig)

    seller = sub.add_parser("seller", help="Read seller profiles (with their gigs and reviews)")
    seller.add_argument("sellers", nargs="+", metavar="SELLER", help="Username or profile URL")
    seller.add_argument(
        "--gigs", action="store_true", help="Output the sellers' gigs instead of the profiles"
    )
    _add_common(seller)
    _add_output(seller)

    filters = sub.add_parser("filters", help="List the filters Fiverr offers for a listing")
    filters.add_argument("query", nargs="?", help="Search words")
    filters.add_argument("--url", help="A Fiverr search or category URL")
    filters.add_argument("--json", action="store_true", help="Print the filters as JSON")
    _add_common(filters)
    return parser


def _filters_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "seller_level": args.seller_level,
        "seller_country": args.seller_country,
        "seller_language": args.seller_language,
        "delivery_days": args.delivery_days,
        "min_price": args.min_price,
        "max_price": args.max_price,
        "pro": args.pro,
        "online": args.online,
        "agency": args.agency,
        "hourly": args.hourly,
        "facets": args.facet,
    }


def order_gigs(gigs: list[Gig], order: str | None) -> list[Gig]:
    """Gigs sorted by ``price``, ``price-desc``, ``rating``, ``reviews`` or ``delivery``;
    gigs without the value go last."""
    if not order:
        return gigs
    key, reverse = ORDERS[order]
    known = [gig for gig in gigs if key(gig) is not None]
    unknown = [gig for gig in gigs if key(gig) is None]
    return sorted(known, key=key, reverse=reverse) + unknown


def _render(records: list[Any], args: argparse.Namespace) -> str:
    if args.format == "jsonl":
        return to_jsonl(records)
    if args.format == "csv":
        if records and all(isinstance(r, GigDetails) for r in records):
            return csv_string(package_rows(records), PACKAGE_COLUMNS)
        return csv_string(records)
    return to_json(records, pretty=args.pretty) + "\n"


def _emit(records: list[Any], args: argparse.Namespace) -> None:
    text = _render(records, args)
    if args.output:
        encoding = "utf-8-sig" if args.format == "csv" else "utf-8"
        with open(Path(args.output), "w", encoding=encoding, newline="") as handle:
            handle.write(text)
        _log(args, f"wrote {len(records)} record(s) to {args.output}")
    else:
        _stdout().write(text)


def _scraper(args: argparse.Namespace) -> FiverrScraper:
    def on_retry(attempt: int, delay: float, error: BaseException) -> None:
        _log(args, f"  retry {attempt} in {delay:.0f}s ({type(error).__name__}: {error})")

    return FiverrScraper(country=args.country, retries=args.retries, on_retry=on_retry)


def _cmd_search(args: argparse.Namespace, scraper: FiverrScraper | None) -> int:
    if not args.queries and not args.url:
        raise SystemExit("search: give search words or --url")
    if args.queries and args.url:
        raise SystemExit("search: give search words or --url, not both")
    filters = _filters_from_args(args)
    if args.dry_run:
        for query in args.queries or [None]:
            url = listing_page_url(query, url=args.url, sort=args.sort, **filters)
            _stdout().write(url + "\n")
        return 0
    scraper = scraper or _scraper(args)

    def on_page(page: SearchPage) -> None:
        total = f" of {page.total:,}" if page.total is not None else ""
        _log(
            args,
            f"  page {page.page}: {len(page.gigs)} gigs ({len(page.organic)} organic){total}",
        )

    options = {
        "pages": args.pages,
        "limit": args.limit,
        "sort": args.sort,
        "skip_sponsored": args.skip_sponsored,
        "min_rating": args.min_rating,
        "min_reviews": args.min_reviews,
        "check_filters": not args.no_check_filters,
        "on_page": on_page,
        **filters,
    }
    seen: set[int] = set()
    gigs: list[Gig] = []
    for query in args.queries or [None]:
        _log(args, f"searching {query!r}" if query else f"reading {args.url}")
        found = scraper.search(query, url=args.url, seen=seen, **options)
        _log(args, f"  {len(found)} gig(s)")
        gigs.extend(found)
    gigs = order_gigs(gigs, args.order)
    if not args.details:
        _emit(gigs, args)
        return 0
    details = scraper.gigs(
        gigs, on_error=lambda url, exc: _log(args, f"  skipped {url}: {type(exc).__name__}: {exc}")
    )
    _emit(details, args)
    return 0


def _cmd_gig(args: argparse.Namespace, scraper: FiverrScraper | None) -> int:
    scraper = scraper or _scraper(args)
    failures = 0

    def on_error(item: str, exc: Exception) -> None:
        nonlocal failures
        failures += 1
        _log(args, f"  {item}: {type(exc).__name__}: {exc}")

    details = scraper.gigs(args.gigs, on_error=on_error)
    _emit(details, args)
    return 1 if failures and not details else 0


def _cmd_seller(args: argparse.Namespace, scraper: FiverrScraper | None) -> int:
    scraper = scraper or _scraper(args)
    profiles = []
    for name in args.sellers:
        try:
            profiles.append(scraper.seller(name))
        except FiverrError as exc:
            _log(args, f"  {name}: {type(exc).__name__}: {exc}")
    if args.gigs:
        _emit([gig for profile in profiles for gig in profile.gigs], args)
    else:
        _emit(profiles, args)
    return 0 if profiles else 1


def _cmd_filters(args: argparse.Namespace, scraper: FiverrScraper | None) -> int:
    if not args.query and not args.url:
        raise SystemExit("filters: give search words or --url")
    scraper = scraper or _scraper(args)
    page = scraper.filters(args.query, url=args.url)
    out = _stdout()
    if args.json:
        out.write(json.dumps([g.to_dict() for g in page.filters], ensure_ascii=False, indent=2))
        out.write("\n")
        return 0
    where = page.sub_category or page.category or ""
    total = f"{page.total:,} gigs" if page.total is not None else "gigs"
    out.write(f"{where} - {total} - pass as --facet KEY=VALUE\n")
    for group in page.filters:
        label = f" ({group.label})" if group.label else ""
        if not group.options:
            hint = "use --min-price / --max-price" if group.key == "gig_price_range" else ""
            out.write(f"\n{group.key}{label} {hint}\n".rstrip() + "\n")
            continue
        out.write(f"\n{group.key}{label}{' [multi]' if group.multi else ''}\n")
        for option in group.options[:OPTIONS_SHOWN]:
            count = f"  {option.count:,}" if option.count is not None else ""
            name = f"  {option.label}" if option.label and option.label != option.value else ""
            out.write(f"  {option.value}{name}{count}\n")
        if len(group.options) > OPTIONS_SHOWN:
            out.write(f"  ... {len(group.options) - OPTIONS_SHOWN} more (use --json)\n")
    return 0


COMMANDS = {
    "search": _cmd_search,
    "gig": _cmd_gig,
    "seller": _cmd_seller,
    "filters": _cmd_filters,
}


def main(argv: Sequence[str] | None = None, *, scraper: FiverrScraper | None = None) -> int:
    """Run the CLI. ``scraper`` lets tests inject a scraper with a mocked client."""
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args, scraper)
    except (FiverrError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if not type(exc).__module__.startswith("scrapeunblocker"):
            raise
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)  # API errors, e.g. a bad key
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
