"""Pricing research: the cheapest gigs from top-rated and level 2 sellers.

Collects two pages of a search, keeping only top-rated and level 2 sellers in
the given countries who deliver within 3 days (all applied by Fiverr itself),
then sorts the gigs by starting price and writes them to a CSV file.

    python examples/top_rated_to_csv.py "logo design" --country US GB
"""

from __future__ import annotations

import argparse
import statistics

from fiverr_scraper import FiverrScraper, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", nargs="?", default="logo design")
    parser.add_argument("--country", nargs="+", default=["US"], help="Seller countries")
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("-o", "--output", default="top-rated-gigs.csv")
    args = parser.parse_args()

    fiverr = FiverrScraper()
    gigs = fiverr.search(
        args.query,
        pages=args.pages,
        seller_level=["top_rated", "level_2"],
        seller_country=args.country,
        delivery_days=3,
        skip_sponsored=True,
    )
    gigs.sort(key=lambda gig: (gig.price is None, gig.price or 0))
    write_csv(gigs, args.output)

    prices = [gig.price for gig in gigs if gig.price is not None]
    print(f"{len(gigs)} gigs written to {args.output}")
    if prices:
        print(
            f"starting prices: min ${min(prices):g}, median ${statistics.median(prices):g}, "
            f"max ${max(prices):g}"
        )
    for gig in gigs[:5]:
        print(f"  ${gig.price:g}  {gig.rating} ({gig.reviews})  {gig.seller_username}: {gig.title}")


if __name__ == "__main__":
    main()
