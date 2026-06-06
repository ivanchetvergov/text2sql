from __future__ import annotations

from typing import Any

from .constants import NOTE_STOP_PREFIXES


def _col_note(retrieval_text: str) -> str:
    if not retrieval_text:
        return ""

    rt = retrieval_text.strip().lower()
    if any(rt.startswith(prefix) for prefix in NOTE_STOP_PREFIXES):
        return ""

    note = retrieval_text.split(",")[0].split(".")[0].strip()
    return note[:40] if len(note) > 3 else ""


def _split_cols(cols_str: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    buffer: list[str] = []
    for ch in cols_str:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1

        if ch == "," and depth == 0:
            parts.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(ch)

    if buffer:
        parts.append("".join(buffer).strip())
    return parts


def enrich_ddl(context_text: str, columns_cfg: dict[str, Any]) -> str:
    if not context_text or not columns_cfg:
        return context_text

    paren = context_text.find("(")
    if paren == -1:
        return context_text

    table_part = context_text[:paren]
    cols_str = context_text[paren + 1 :].rstrip(")")

    enriched: list[str] = []
    for segment in _split_cols(cols_str):
        segment = segment.strip()
        col_name = segment.split()[0] if segment else ""
        note = _col_note(columns_cfg.get(col_name, {}).get("retrieval_text", ""))
        enriched.append(f"{segment} -- {note}" if note else segment)

    return f"{table_part}({', '.join(enriched)})"
