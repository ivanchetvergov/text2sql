from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .constants import DOC_FIELDS

_TOKEN_RE = re.compile(r"[\w\u0400-\u04FF]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text or "")]


def doc_key(item: dict[str, Any]) -> str:
    return f"{item.get('kind')}:{item.get('table')}:{item.get('example_id')}:{hash(item.get('text', ''))}"


def copy_doc(item: dict[str, Any]) -> dict[str, Any]:
    return {field: item.get(field) for field in DOC_FIELDS}


def count_kinds(items: list[dict[str, Any]]) -> Counter[str]:
    return Counter(item.get("kind", "") for item in items)
