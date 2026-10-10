# Fiverr Scraper

[![CI](https://github.com/ScrapeUnblocker/fiverr-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/ScrapeUnblocker/fiverr-scraper/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by ScrapeUnblocker](https://img.shields.io/badge/powered%20by-ScrapeUnblocker-6f42c1.svg)](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)

**Scrape [Fiverr](https://www.fiverr.com) gigs, gig packages and seller profiles into clean
JSON or CSV: starting prices, Basic / Standard / Premium package prices, delivery times and
revisions, ratings and review counts, seller level, country, languages and response time.**
Search by keyword or paste any Fiverr search or category URL, use Fiverr's own filters
(seller level, seller country and language, delivery time, budget, Pro, online now, agency,
hourly, plus every category-specific filter), and collect several pages and queries in one
run. Built for freelance pricing research, competitor analysis, market sizing and
finding the right seller.

Powered by [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos):
the `getPageSource` API loads each Fiverr page in a real browser and returns the rendered
HTML. This package reads the data Fiverr embeds in its pages and turns it into typed
records. You don't need a Fiverr account, proxies, a headless browser or retry logic of
your own.

## Features

- **Search or browse any listing.** Pass search words, or paste any Fiverr search or
  category URL from your browser (filters already in the URL are kept). Several queries
  in one run are merged and de-duplicated by gig ID.
- **Fiverr's own filters.** Seller level (Top Rated, Level 2, Level 1, New), seller
  country, seller language, delivery time (24h, 3 or 7 days), budget range, Fiverr Pro,
  sellers online now, agencies, gigs with an hourly rate, and any category filter Fiverr
  shows in the sidebar (logo style, file format, service offerings, ...). The `filters`
  command lists every filter and value of a listing with gig counts.
- **Filters are verified.** Fiverr echoes back filter names and values it does not know
  without applying them. Every requested filter is checked against the filters the
  listing actually offers, and the sort order against the one the page reports, so a typo
  raises an error instead of returning unfiltered gigs.
- **Clean gig records.** Gig ID, title, URL, starting price in USD, delivery days, number of
  packages, hourly rate, rating and review count, seller username, display name, country,
  level, rating, review count, languages and online status, agency, Pro / Fiverr's Choice /
  sponsored flags, subscription and consultation offers, category IDs, attributes (style,
  file formats, ...), images, video and position on the page.
- **Sponsored slots handled.** Fiverr mixes sponsored slots into every page and repeats
  some gigs in them. Each gig is returned once; a gig that also ranks organically keeps its
  organic position, and `--skip-sponsored` drops gigs that only appear as ads.
- **Gig details.** Every package with its name, description, price, delivery time,
  revisions (including "unlimited"), included features and extra-fast delivery add-on;
  subscription discounts, paid consultation prices, the full description, attributes, FAQ,
  tags, star breakdown, communication / quality / value ratings, orders in queue,
  favorites count, the latest reviews (rating, text, reviewer country, order price range
  and duration, seller response) and the seller's stats (level, member since, response
  time, completed orders, last delivery, languages).
- **Seller profiles.** Level, rating and review count, country, timezone, member since,
  response time, languages, skills, education, certifications, every gig of the seller and
  their latest reviews.
- **Resilient.** Timeouts, transient API errors and pages that come back without their data
  are retried with doubling backoff. Unknown sellers and removed gigs raise a clear
  not-found error.
- **JSON, JSON Lines or CSV.** CSV files are UTF-8 with a BOM, so Excel opens them correctly.
  Gig details export one CSV row per package, ready for a pricing spreadsheet.
- **CLI + Python library.** Fully typed, and tested offline with a mocked client.

## Install

```bash
git clone https://github.com/ScrapeUnblocker/fiverr-scraper.git
cd fiverr-scraper
pip install .
```

Get an API key at [scrapeunblocker.com](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
and expose it as `SCRAPEUNBLOCKER_KEY` (the official SDK reads it from there):

```bash
export SCRAPEUNBLOCKER_KEY=your_key_here        # Windows PowerShell: $env:SCRAPEUNBLOCKER_KEY="your_key_here"
```

You can also copy `.env.example` to `.env` and load it with your tool of choice.

## CLI usage

```bash
# Logo design gigs, 2 pages, to CSV
fiverr-scraper search "logo design" -p 2 -f csv -o logo-design.csv

# Top Rated and Level 2 sellers from the US or UK who deliver within 3 days, under $50
fiverr-scraper search "logo design" --seller-level top_rated level_2 \
    --seller-country US GB --delivery-days 3 --max-price 50 --pretty

# Best-selling WordPress gigs from English-speaking sellers, cheapest first (sorted locally)
fiverr-scraper search "wordpress website" --sort best_selling --seller-language en --order price

# Any category URL from the browser, newest gigs first, Fiverr Pro only
fiverr-scraper search --url "https://www.fiverr.com/categories/graphics-design/creative-logo-design" \
    --sort newest --pro

# Several queries in one run, merged and de-duplicated, without sponsored-only gigs
fiverr-scraper search "podcast editing" "audio editing" --skip-sponsored -f jsonl -o audio.jsonl

# What can I filter on? Every filter and value of a listing, with gig counts
fiverr-scraper filters "logo design"
fiverr-scraper search "logo design" --facet style=flat_minimalist --facet file_format=svg

# Gig details: packages, FAQ, reviews, seller stats (CSV = one row per package)
fiverr-scraper gig https://www.fiverr.com/<seller>/<gig-slug> --pretty
fiverr-scraper search "voice over" -n 10 --details -f csv -o voice-over-packages.csv

# Seller profiles, or all gigs of some sellers
fiverr-scraper seller <username> --pretty
fiverr-scraper seller <username> <another-username> --gigs -f csv -o seller-gigs.csv

# Show the URL that would be fetched, without calling the API
fiverr-scraper search "seo audit" --seller-level top_rated --dry-run
```

`search` options:

| Option | Meaning |
| --- | --- |
| `QUERY ...` / `--url URL` | Search words (several allowed) or a Fiverr search / category URL |
| `--sort` | `relevance` (default), `best_selling`, `newest` |
| `--seller-level LEVEL ...` | `top_rated`, `level_2`, `level_1`, `new` |
| `--seller-country CODE ...` | Seller lives in these countries (`US`, `GB`, `DE`, ...) |
| `--seller-language CODE ...` | Seller speaks these languages (`en`, `de`, `es`, ...) |
| `--delivery-days {1,3,7}` | Delivered within 1 (express 24h), 3 or 7 days |
| `--min-price`, `--max-price` | Budget range of the starting price, in USD |
| `--pro`, `--online`, `--agency`, `--hourly` | Fiverr Pro only, sellers online now, agencies only, gigs with an hourly rate |
| `--facet KEY=VALUE` | Any other filter from the `filters` command (repeatable; `KEY=a,b` for several values) |
| `--skip-sponsored` | Drop gigs that only appear in sponsored slots |
| `--min-rating N`, `--min-reviews N` | Keep gigs with at least this rating / review count |
| `--order` | Sort the collected gigs locally: `price`, `price-desc`, `rating`, `reviews`, `delivery` |
| `-p, --pages N` | Pages per query (stops at the last page) |
| `-n, --limit N` | At most N gigs per query |
| `--details` | Also read every gig page (one extra request per gig) |
| `--no-check-filters` | Do not fail when Fiverr does not apply a sort or filter |
| `--country CODE` | Country the requests are routed through (default `us`) |
| `-f, --format` | `json` (default), `jsonl` or `csv`; `-o FILE` to write a file, `--pretty` to indent |

Fiverr ranks gigs for the visitor's country, so `--country` changes the order and the
totals; prices are always returned in USD, the currency Fiverr stores them in.

## Library usage

```python
from fiverr_scraper import FiverrScraper, packages_to_csv, write_csv

fiverr = FiverrScraper()  # reads SCRAPEUNBLOCKER_KEY; FiverrScraper(api_key="...") also works

gigs = fiverr.search(
    "logo design",
    pages=2,
    seller_level=["top_rated", "level_2"],
    seller_country=["US", "GB"],
    delivery_days=3,
    max_price=100,
    skip_sponsored=True,
)
for gig in gigs[:5]:
    print(gig.price, gig.rating, gig.reviews, gig.seller_level, gig.title, gig.url)
write_csv(gigs, "logo-design.csv")

# Any category or search URL, plus category-specific filters
page = fiverr.filters(url="https://www.fiverr.com/categories/graphics-design/creative-logo-design")
print([group.key for group in page.filters])  # style, logo_type, file_format, ...
minimal = fiverr.search(url=page.url, facets={"style": "flat_minimalist"}, sort="best_selling")

# Several searches, de-duplicated by gig ID
gigs = fiverr.search_many(["podcast editing", "audio editing"], pages=2)

# Gig details: packages, FAQ, reviews and the seller
details = fiverr.gig(gigs[0])  # or a gig URL / "seller/gig-slug"
basic = details.package("basic")
print(basic.price, basic.delivery_days, basic.revisions, basic.features)
print(details.seller.level, details.seller.completed_orders, details.star_counts)
packages_to_csv(fiverr.gigs(gigs[:10]), "packages.csv")  # one row per package

# Seller profiles
profile = fiverr.seller("some_username")
print(profile.level, profile.rating, profile.languages, len(profile.gigs))
```

Errors: `FiverrNotFoundError` (no such gig or seller), `FiverrFilterError` (Fiverr did not
apply a requested sort or filter) and `FiverrParseError` (a page came back without its data
after all retries) all derive from `FiverrError`. API errors from the official SDK (for
example an invalid key) are passed through.

## Example output

One gig from `fiverr-scraper search "logo design" --seller-level top_rated level_2
--seller-country US --delivery-days 3 --max-price 50` (seller identity replaced, image lists
shortened):

```json
{
  "gig_id": 489432662,
  "title": "do a premium minimalist logo design and brand identity",
  "url": "https://www.fiverr.com/example_seller/do-a-premium-minimalist-logo-design-and-brand-identity",
  "price": 25.0,
  "currency": "USD",
  "delivery_days": 2,
  "packages": 3,
  "hourly_rate": null,
  "rating": 4.98,
  "reviews": 114,
  "seller_username": "example_seller",
  "seller_name": "Example",
  "seller_id": 123456789,
  "seller_country": "US",
  "seller_level": "level_two_seller",
  "seller_rating": 4.98,
  "seller_reviews": 114,
  "seller_online": false,
  "seller_languages": ["en", "es", "fr", "de"],
  "seller_url": "https://www.fiverr.com/example_seller",
  "agency": null,
  "pro": false,
  "fiverr_choice": false,
  "sponsored": false,
  "offers_consultation": false,
  "offers_subscription": true,
  "subscription_discount": 10,
  "category_id": 3,
  "sub_category_id": 49,
  "attributes": {
    "style": ["flat_minimalist"],
    "logo_type": ["monogram", "wordmark", "pictorial"],
    "file_format": ["ai", "jpg", "pdf", "png", "psd", "eps", "cdr", "svg"]
  },
  "image": "https://fiverr-res.cloudinary.com/t_main1,q_auto,f_auto/gigs/489432662/original/87c45833b37715d322b053bf8058805acd0c4831.jpg",
  "position": 6,
  "page": 1,
  "query": "logo design"
}
```

One package and one review from `fiverr-scraper gig <url>`:

```json
{
  "tier": "basic",
  "name": "1 CUSTOM MINIMALIST LOGO CONCEPT",
  "description": "1 Minimalist Logo Concept\nTransparent PNG, AI, EPS & SVG Vector Files, High-Resolution Files,",
  "price": 20.0,
  "delivery_days": 2,
  "revisions": 2,
  "features": ["Number of concepts included: 1", "Logo transparency", "Vector file",
               "Printable file", "3D mockup", "Source file"],
  "extra_fast_price": 10.0,
  "extra_fast_days": 1
}
```

```json
{
  "rating": 5.0,
  "comment": "Excellent work from the start. The logo has a strong architectural feel, and the building icon fits the brand perfectly. Very satisfied with the final result!",
  "reviewer_country": "United States",
  "created_at": "2026-07-28T20:50:45",
  "order_price_range": "Up to $50",
  "order_duration_days": 8,
  "repeat_buyer": false,
  "business": true
}
```

## Good to know

- **Prices** are USD. `price` on a gig card is the "From" price Fiverr shows (its cheapest
  package); `price_min` / `price_max` on gig details span all packages.
- **Sort orders.** `relevance`, `best_selling` and `newest` are Fiverr's own. Fiverr's price
  sort did not order the results by price, so it is not offered; use `--order price` (or
  sort the returned list) to order collected gigs locally.
- **Pagination.** A page has 48 slots, part of them sponsored. Collection stops at the last
  page: past it Fiverr only serves sponsored slots, which this package detects.
- **Reviews.** Gig pages and seller profiles embed the latest reviews (five on the pages
  tested), plus the full star breakdown and review count.
- **Seller levels** are normalized to `top_rated_seller`, `level_two_seller`,
  `level_one_seller` and `new_seller`; language levels to `basic`, `conversational`,
  `fluent` and `native_or_bilingual`.
- Collect public data responsibly: keep request volumes reasonable and follow Fiverr's
  terms and the data-protection rules that apply to you, especially for seller and
  reviewer names.

## Project layout

```
fiverr-scraper/
├── src/fiverr_scraper/
│   ├── __init__.py      # package exports + __version__
│   ├── scraper.py       # FiverrScraper: search, filters, gig pages, seller profiles, retries
│   ├── parsing.py       # embedded page data -> typed records
│   ├── models.py        # Gig, SearchPage, GigDetails, Package, Review, SellerProfile, ...
│   ├── urls.py          # search / category / gig / seller URLs and Fiverr's ref filters
│   ├── export.py        # JSON, JSON Lines and CSV writers
│   ├── cli.py           # the fiverr-scraper command
│   └── __main__.py      # python -m fiverr_scraper
├── examples/
│   ├── search_to_json.py     # one page of results as JSON
│   ├── top_rated_to_csv.py   # pricing research: top-rated sellers, cheapest first, to CSV
│   └── gig_packages.py       # compare the Basic / Standard / Premium packages of a gig
├── tests/                    # offline tests with a mocked client (no API calls)
├── pyproject.toml
├── requirements.txt
├── Makefile
└── .github/workflows/ci.yml
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make install    # pip install -e ".[dev]"
make lint       # ruff check .
make format     # ruff format .
make test       # pytest -q (offline, no API key needed)
make run        # examples/search_to_json.py "logo design" (needs SCRAPEUNBLOCKER_KEY)
```

`pre-commit install` enables the ruff hooks from `.pre-commit-config.yaml`.

## Links

- [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos) - web scraping API that returns rendered HTML from protected sites
- [Documentation](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos) - `getPageSource`, SDKs, parameters and errors
- Official SDK: `pip install scrapeunblocker`

## License

[MIT](LICENSE) - Copyright (c) 2026 ScrapeUnblocker
