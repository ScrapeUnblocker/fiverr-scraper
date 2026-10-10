"""Search Fiverr and print the gigs of the first results page as JSON.

python examples/search_to_json.py "logo design"
python examples/search_to_json.py "wordpress website" --sort best_selling
"""

from __future__ import annotations

import argparse
import json

from fiverr_scraper import FiverrScraper


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", nargs="?", default="logo design")
    parser.add_argument("--sort", default=None, help="relevance, best_selling or newest")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    fiverr = FiverrScraper()  # reads SCRAPEUNBLOCKER_KEY from the environment
    gigs = fiverr.search(args.query, sort=args.sort, limit=args.limit)
    print(json.dumps([gig.to_dict() for gig in gigs], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
