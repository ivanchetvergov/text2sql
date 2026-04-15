from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .constants import DOC_FIELDS

_TOKEN_RE = re.compile(r"[\w\u0400-\u04FF]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text or "")]


def normalise_scores(items: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    if not items:
        return items

    hi = max(float(item.get(field, 0.0)) for item in items)
    lo = min(float(item.get(field, 0.0)) for item in items)
    span = hi - lo
    for item in items:
        score = float(item.get(field, 0.0))
        item[f"{field}_norm"] = (score - lo) / span if span > 1e-12 else (1.0 if hi > 0 else 0.0)
    return items


def doc_key(item: dict[str, Any]) -> str:
    return f"{item.get('kind')}:{item.get('table')}:{item.get('example_id')}:{hash(item.get('text', ''))}"


def copy_doc(item: dict[str, Any]) -> dict[str, Any]:
    return {field: item.get(field) for field in DOC_FIELDS}


def count_kinds(items: list[dict[str, Any]]) -> Counter[str]:
    return Counter(item.get("kind", "") for item in items)
