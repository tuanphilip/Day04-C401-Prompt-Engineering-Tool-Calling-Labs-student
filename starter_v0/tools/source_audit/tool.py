from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
WEAK_SOURCE_HINTS = {"unknown", "social", "x.com", "twitter", "reddit", "forum", "blog"}


def _urls_from_markdown(markdown: str) -> list[str]:
    return [match.rstrip(".,;:") for match in URL_RE.findall(markdown or "")]


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.")


def _item_label(item: dict[str, Any], index: int) -> str:
    title = str(item.get("title") or "").strip()
    return title or f"item_{index + 1}"


def source_audit(
    markdown: str = "",
    items: list[dict[str, Any]] | None = None,
    min_sources: int = 2,
) -> dict[str, Any]:
    items = items or []
    min_sources = max(1, int(min_sources or 2))

    urls = set(_urls_from_markdown(markdown))
    missing_urls: list[str] = []
    weak_sources: list[str] = []

    for index, item in enumerate(items):
        url = str(item.get("url") or "").strip()
        source = str(item.get("source") or "").strip().lower()
        label = _item_label(item, index)

        if url:
            urls.add(url)
        else:
            missing_urls.append(label)

        source_hint = source or _domain(url)
        if source_hint and any(hint in source_hint for hint in WEAK_SOURCE_HINTS):
            weak_sources.append(label)

    domains = sorted({_domain(url) for url in urls if _domain(url)})
    warnings: list[str] = []

    if len(domains) < min_sources:
        warnings.append(f"Expected at least {min_sources} distinct source domains; found {len(domains)}.")
    if missing_urls:
        warnings.append(f"{len(missing_urls)} item(s) are missing URLs.")
    if weak_sources:
        warnings.append(f"{len(weak_sources)} item(s) may need stronger source review.")
    if not urls and not items:
        warnings.append("No URLs or structured items were provided for auditing.")

    checklist = [
        {"name": "has_source_urls", "passed": bool(urls)},
        {"name": "meets_min_source_count", "passed": len(domains) >= min_sources},
        {"name": "all_items_have_urls", "passed": not missing_urls},
        {"name": "weak_sources_reviewed", "passed": not weak_sources},
    ]

    status = "pass" if all(item["passed"] for item in checklist) else "needs_review"

    return {
        "tool": "source_audit",
        "status": status,
        "source_count": len(urls),
        "distinct_domains": domains,
        "missing_url_count": len(missing_urls),
        "missing_url_items": missing_urls,
        "weak_source_items": weak_sources,
        "warnings": warnings,
        "checklist": checklist,
    }
