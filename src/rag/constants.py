from __future__ import annotations

from typing import Final

CANDIDATES_PER_SLOT: Final[dict[str, int]] = {"tables": 14, "examples": 10}
MINIMUMS_PER_SLOT: Final[dict[str, int]] = {"tables": 4, "examples": 2}
KIND_PER_SLOT: Final[dict[str, str]] = {"tables": "table", "examples": "example"}
DOC_FIELDS: Final[tuple[str, ...]] = (
    "kind",
    "text",
    "context_text",
    "table",
    "example_id",
    "_score",
)
NOTE_STOP_PREFIXES: Final[set[str]] = {
    "уникальный идентификатор",
    "первичный ключ",
    "FK на",
    "fk на",
}
