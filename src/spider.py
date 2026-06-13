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
import re
from pathlib import Path
from typing import Any


_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "spider"


class SpiderLoader:
    def __init__(self, spider_root: str | Path, docs_dir: str | Path | None = None) -> None:
        self._root = Path(spider_root)
        self._docs_dir = Path(docs_dir) if docs_dir else _DOCS_DIR
        self._tables: list[dict] | None = None
        self._splits: dict[str, list[dict]] = {}

    # ── public API ────────────────────────────────────────────────────────────

    def schema_for(
        self,
        db_id: str,
        train_split: str = "train",
        attach_examples: bool = True,
    ) -> tuple[list[dict], dict]:
        """Return (rag_entries, graph_data) for a Spider database.

        Loads from docs/spider/{db_id}.json if available (pre-built, enriched),
        otherwise falls back to generating from tables.json on the fly.
        """
        doc_path = self._docs_dir / f"{db_id}.json"
        if doc_path.exists():
            return self._load_from_docs(doc_path, db_id, train_split, attach_examples)

        db = self._find_db(db_id)
        rag_entries = self._rag_entries(db)
        if attach_examples:
            self._attach_examples(rag_entries, db_id, train_split)
        return rag_entries, self._graph_data(db)

    def _load_from_docs(
        self, doc_path: Path, db_id: str, train_split: str, attach_examples: bool
    ) -> tuple[list[dict], dict]:
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
        rag_entries = doc["entries"]
        if attach_examples:
            self._attach_examples(rag_entries, db_id, train_split)
        db = self._find_db(db_id)
        return rag_entries, self._graph_data(db)

    def questions_for(self, db_id: str, split: str = "dev") -> list[dict]:
        """Return benchmark cases for a specific database and split."""
        if split not in self._splits:
            with (self._root / f"{split}.json").open(encoding="utf-8") as f:
                self._splits[split] = json.load(f)
        all_qs = self._splits[split]
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
        table_names_orig = db["table_names_original"]
        table_names_nl   = db["table_names"]
        col_names_orig   = db["column_names_original"]   # [[tbl_idx, col_name], ...]
        col_names_nl     = db["column_names"]             # [[tbl_idx, nl_name], ...]
        col_types        = db["column_types"]
        primary_keys     = set(db["primary_keys"])

        table_cols: dict[int, list[tuple[int, str, str, str]]] = {
            i: [] for i in range(len(table_names_orig))
        }
        for col_idx, (tbl_idx, col_orig) in enumerate(col_names_orig):
            if tbl_idx == -1:
                continue
            col_nl = col_names_nl[col_idx][1]
            table_cols[tbl_idx].append((col_idx, col_orig, col_names_nl[col_idx][1], col_types[col_idx]))

        entries = []
        for tbl_idx, tbl_name in enumerate(table_names_orig):
            tbl_nl = table_names_nl[tbl_idx]
            cols = table_cols[tbl_idx]
            col_parts = []
            retrieval_parts = []
            for col_idx, col_orig, col_nl, col_type in cols:
                suffix = " PK" if col_idx in primary_keys else ""
                col_parts.append(f"{col_orig} {col_type.upper()}{suffix}")
                retrieval_parts.append(col_nl if col_nl != col_orig else col_orig)

            context_text   = f"{tbl_name}({', '.join(col_parts)})"
            retrieval_text = f"{tbl_nl} ({tbl_name}): {', '.join(retrieval_parts)}"

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

    def _attach_examples(self, entries: list[dict], db_id: str, split: str) -> None:
        """Load training Q&A pairs and attach them to the most relevant table entry."""
        try:
            train_cases = self.questions_for(db_id, split=split)
        except FileNotFoundError:
            return
        if not train_cases:
            return

        by_table: dict[str, list[dict]] = {e["table"]: [] for e in entries}
        _from_re = re.compile(r'\bFROM\s+(\w+)', re.IGNORECASE)

        for case in train_cases:
            sql = case.get("expected_sql", "")
            m = _from_re.search(sql)
            tbl = m.group(1).lower() if m else None
            target = next((e["table"] for e in entries if e["table"].lower() == tbl), None)
            if target is None and entries:
                target = entries[0]["table"]
            if target:
                by_table[target].append({"query": case["question"], "answer": sql})

        for entry in entries:
            entry["examples"] = by_table.get(entry["table"], [])

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
