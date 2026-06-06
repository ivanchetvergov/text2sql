"""Spider dataset adapter.

Loads Spider schema (tables.json) and questions (train/dev.json) and converts
them into the formats expected by RAG.build_from_entries() and
KnowledgeGraph.load_from_dict(), so the pipeline works on any Spider database
without writing any YAML by hand.

Usage example:
    loader = SpiderLoader(spider_root="path/to/spider")
    rag_entries, graph_data = loader.schema_for("concert_singer")
    questions = loader.questions_for("concert_singer", split="dev")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SpiderLoader:
    def __init__(self, spider_root: str | Path) -> None:
        self._root = Path(spider_root)
        self._tables: list[dict] | None = None

    # ── public API ────────────────────────────────────────────────────────────

    def schema_for(self, db_id: str) -> tuple[list[dict], dict]:
        """Return (rag_entries, graph_data) for a Spider database."""
        db = self._find_db(db_id)
        return self._rag_entries(db), self._graph_data(db)

    def questions_for(self, db_id: str, split: str = "dev") -> list[dict]:
        """Return benchmark cases for a specific database and split."""
        path = self._root / f"{split}.json"
        with path.open(encoding="utf-8") as f:
            all_qs: list[dict] = json.load(f)
        return [
            {
                "id": f"spider_{i:04d}",
                "question": q["question"],
                "expected_sql": q.get("query", ""),
                "db_id": q["db_id"],
            }
            for i, q in enumerate(all_qs)
            if q["db_id"] == db_id
        ]

    def all_db_ids(self) -> list[str]:
        return [db["db_id"] for db in self._load_tables()]

    # ── schema conversion ─────────────────────────────────────────────────────

    def _rag_entries(self, db: dict) -> list[dict]:
        table_names = db["table_names_original"]
        col_names   = db["column_names_original"]   # [[tbl_idx, col_name], ...]
        col_types   = db["column_types"]
        primary_keys = set(db["primary_keys"])

        table_cols: dict[int, list[tuple[int, str, str]]] = {
            i: [] for i in range(len(table_names))
        }
        for col_idx, (tbl_idx, col_name) in enumerate(col_names):
            if tbl_idx == -1:
                continue
            table_cols[tbl_idx].append((col_idx, col_name, col_types[col_idx]))

        entries = []
        for tbl_idx, tbl_name in enumerate(table_names):
            cols = table_cols[tbl_idx]
            col_parts = []
            for col_idx, col_name, col_type in cols:
                suffix = " PK" if col_idx in primary_keys else ""
                col_parts.append(f"{col_name} {col_type.upper()}{suffix}")

            context_text   = f"{tbl_name}({', '.join(col_parts)})"
            retrieval_text = f"{tbl_name}: {', '.join(c[1] for c in cols)}"

            entries.append({
                "table":          tbl_name,
                "retrieval_text": retrieval_text,
                "context_text":   context_text,
                "columns":        {},
                "examples":       [],
            })
        return entries

    def _graph_data(self, db: dict) -> dict[str, Any]:
        table_names  = db["table_names_original"]
        col_names    = db["column_names_original"]
        primary_keys = set(db["primary_keys"])
        foreign_keys = db["foreign_keys"]   # [[from_col_idx, to_col_idx], ...]

        # PK name per table
        table_pk: dict[int, str] = {}
        for pk_idx in primary_keys:
            if pk_idx < len(col_names):
                tbl_idx, col_name = col_names[pk_idx]
                if tbl_idx != -1:
                    table_pk[tbl_idx] = col_name

        tables: dict[str, Any] = {}
        for tbl_idx, tbl_name in enumerate(table_names):
            tables[tbl_name] = {
                "pk":        table_pk.get(tbl_idx, "id"),
                "hub_score": 3,
                "edges":     [],
            }

        for from_col_idx, to_col_idx in foreign_keys:
            if from_col_idx >= len(col_names) or to_col_idx >= len(col_names):
                continue
            from_tbl_idx, from_col = col_names[from_col_idx]
            to_tbl_idx,   to_col   = col_names[to_col_idx]
            if from_tbl_idx == -1 or to_tbl_idx == -1:
                continue
            tables[table_names[from_tbl_idx]]["edges"].append({
                "to":              table_names[to_tbl_idx],
                "from_col":        from_col,
                "to_col":          to_col,
                "cardinality":     "many_to_one",
                "join_preference": "JOIN",
            })

        return {
            "algorithms": {
                "hub_score_step_cost":  0.12,
                "cardinality_costs":    {"one_to_one": 0.0, "many_to_one": 0.05, "one_to_many": 0.10},
                "reverse_edge_multiplier": 1.5,
            },
            "tables": tables,
        }

    # ── internals ─────────────────────────────────────────────────────────────

    def _load_tables(self) -> list[dict]:
        if self._tables is None:
            with (self._root / "tables.json").open(encoding="utf-8") as f:
                self._tables = json.load(f)
        return self._tables

    def _find_db(self, db_id: str) -> dict:
        for db in self._load_tables():
            if db["db_id"] == db_id:
                return db
        raise ValueError(f"Database '{db_id}' not found in tables.json")
