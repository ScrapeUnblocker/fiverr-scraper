"""Compare the Basic / Standard / Premium packages of a gig.

Pass a gig URL, or search words to read the best-selling gig for them.

    python examples/gig_packages.py https://www.fiverr.com/<seller>/<gig-slug>
    python examples/gig_packages.py "podcast editing"
"""

from __future__ import annotations

import sys

from fiverr_scraper import FiverrScraper


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "podcast editing"
    fiverr = FiverrScraper()
    if "fiverr.com/" not in target:
        found = fiverr.search(target, sort="best_selling", skip_sponsored=True, limit=1)
        if not found:
            sys.exit(f"no gigs found for {target!r}")
        target = found[0].url

    gig = fiverr.gig(target)
    seller = gig.seller
    print(gig.title)
    print(gig.url)
    print(
        f"rating {gig.rating} from {gig.reviews_count} reviews - "
        f"{seller.username} ({seller.level}, {seller.country_code}), "
        f"{seller.completed_orders} orders completed, replies in ~{seller.response_hours}h"
    )
    for package in gig.packages:
        print(
            f"\n[{package.tier}] {package.name} - ${package.price:g}, "
            f"{package.delivery_days} day(s), revisions: {package.revisions}"
        )
        if package.description:
            print(f"  {package.description}")
        for feature in package.features:
            print(f"  + {feature}")
        if package.extra_fast_price:
            print(
                f"  extra-fast: {package.extra_fast_days} day(s) for +${package.extra_fast_price:g}"
            )
    if gig.faq:
        print(f"\nFAQ: {len(gig.faq)} questions, e.g. {gig.faq[0]['question']!r}")


if __name__ == "__main__":
    main()
