"""Write records as JSON, JSON Lines or CSV."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from .models import GigDetails

LIST_SEPARATOR = " | "

#: Columns of the per-package CSV written by :func:`packages_to_csv`.
PACKAGE_COLUMNS = (
    "gig_id",
    "title",
    "seller_username",
    "seller_level",
    "seller_country",
    "rating",
    "reviews_count",
    "tier",
    "name",
    "price",
    "currency",
    "delivery_days",
    "revisions",
    "features",
    "extra_fast_price",
    "extra_fast_days",
    "description",
    "url",
)


def to_dict(record: Any) -> dict[str, Any]:
    """A record (dataclass with ``to_dict`` or a dict) as a plain dict."""
    if hasattr(record, "to_dict"):
        return record.to_dict()
    if isinstance(record, dict):
        return dict(record)
    raise TypeError(f"cannot export {type(record).__name__}")


def to_json(records: Iterable[Any], *, pretty: bool = False) -> str:
    """Serialize records as a JSON array."""
    data = [to_dict(r) for r in records]
    return json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)


def to_jsonl(records: Iterable[Any]) -> str:
    """Serialize records as JSON Lines (one object per line)."""
    return "".join(json.dumps(to_dict(r), ensure_ascii=False) + "\n" for r in records)


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return LIST_SEPARATOR.join("" if item is None else str(item) for item in value)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        if all(isinstance(item, list) for item in value.values()):
            return LIST_SEPARATOR.join(f"{k}: {', '.join(map(str, v))}" for k, v in value.items())
        return json.dumps(value, ensure_ascii=False)
    return value


def flatten(record: Any) -> dict[str, Any]:
    """A record as one flat CSV row: nested records become ``parent_field`` columns,
    lists of values are joined with ``" | "`` and lists of objects become JSON."""
    row: dict[str, Any] = {}
    for key, value in to_dict(record).items():
        if key == "seller" and isinstance(value, dict):
            for sub_key, sub_value in value.items():
                row[f"seller_{sub_key}"] = _cell(sub_value)
        else:
            row[key] = _cell(value)
    return row


def csv_string(records: Iterable[Any], columns: Sequence[str] | None = None) -> str:
    """Records as CSV text (header + one row per record)."""
    rows = [flatten(record) for record in records]
    header: list[str] = list(columns) if columns else []
    if not header:
        for row in rows:
            for key in row:
                if key not in header:
                    header.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in header})
    return buffer.getvalue()


def write_csv(
    records: Iterable[Any], path: str | Path, columns: Sequence[str] | None = None
) -> int:
    """Write records to a UTF-8 CSV file (with a BOM, so Excel reads it). Returns the row count."""
    records = list(records)
    text = csv_string(records, columns)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write(text)
    return len(records)


def package_rows(details: Iterable[GigDetails]) -> list[dict[str, Any]]:
    """One row per gig package: the gig, its seller and the package terms."""
    rows: list[dict[str, Any]] = []
    for gig in details:
        for package in gig.packages:
            rows.append(
                {
                    "gig_id": gig.gig_id,
                    "title": gig.title,
                    "seller_username": gig.seller.username,
                    "seller_level": gig.seller.level,
                    "seller_country": gig.seller.country_code,
                    "rating": gig.rating,
                    "reviews_count": gig.reviews_count,
                    "tier": package.tier,
                    "name": package.name,
                    "price": package.price,
                    "currency": gig.currency,
                    "delivery_days": package.delivery_days,
                    "revisions": package.revisions,
                    "features": package.features,
                    "extra_fast_price": package.extra_fast_price,
                    "extra_fast_days": package.extra_fast_days,
                    "description": package.description,
                    "url": gig.url,
                }
            )
    return rows


def packages_to_csv(details: Iterable[GigDetails], path: str | Path | None = None) -> str:
    """Gig packages as CSV, one row per package (written to ``path`` when given)."""
    rows = package_rows(details)
    text = csv_string(rows, PACKAGE_COLUMNS)
    if path is not None:
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            handle.write(text)
    return text
