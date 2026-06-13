"""
Generate Spider-compatible tables.json, train.json, dev.json from CM/spider data.
Run after the SQLite databases have been created.

Usage:
    python scripts/build_spider_meta.py
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from datasets import load_dataset

SPIDER_DIR = Path(__file__).resolve().parents[1] / "data" / "spider"


# ── tables.json generation ─────────────────────────────────────────────────

def _inspect_db(db_path: Path) -> dict:
    """Extract schema metadata from SQLite file."""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]

    table_names_orig = tables
    table_names_nl = tables  # Spider NL names are same as original for most dbs

    col_names_orig = [[-1, "*"]]
    col_names_nl   = [[-1, "*"]]
    col_types      = ["text"]
    primary_keys   = []
    foreign_keys   = []

    for t_idx, tname in enumerate(tables):
        cur.execute(f"PRAGMA table_info(\"{tname}\")")
        cols = cur.fetchall()  # (cid, name, type, notnull, dflt, pk)
        for col in cols:
            col_names_orig.append([t_idx, col[1]])
            col_names_nl.append([t_idx, col[1]])
            col_types.append(col[2].lower() or "text")
            if col[5]:  # pk flag
                primary_keys.append(len(col_names_orig) - 1)

        cur.execute(f"PRAGMA foreign_key_list(\"{tname}\")")
        fks = cur.fetchall()  # (id, seq, table, from, to, on_update, on_delete, match)
        for fk in fks:
            ref_table = fk[2]
            from_col  = fk[3]
            to_col    = fk[4]
            if ref_table in table_names_orig:
                ref_t_idx = table_names_orig.index(ref_table)
                # find column indices
                from_idx = next(
                    (i for i, c in enumerate(col_names_orig) if c == [t_idx, from_col]), None
                )
                to_idx = next(
                    (i for i, c in enumerate(col_names_orig) if c == [ref_t_idx, to_col]), None
                )
                if from_idx and to_idx:
                    foreign_keys.append([from_idx, to_idx])

    conn.close()
    return {
        "column_names":          col_names_nl,
        "column_names_original": col_names_orig,
        "column_types":          col_types,
        "db_id":                 db_path.parent.name,
        "foreign_keys":          foreign_keys,
        "primary_keys":          primary_keys,
        "table_names":           table_names_nl,
        "table_names_original":  table_names_orig,
    }


def build_tables_json() -> None:
    db_root = SPIDER_DIR / "database"
    entries = []
    for db_dir in sorted(db_root.iterdir()):
        db_file = db_dir / f"{db_dir.name}.db"
        if not db_file.exists():
            print(f"  SKIP {db_dir.name}: no .db file")
            continue
        try:
            entries.append(_inspect_db(db_file))
        except Exception as e:
            print(f"  FAIL {db_dir.name}: {e}")

    out_path = SPIDER_DIR / "tables.json"
    out_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False))
    print(f"tables.json: {len(entries)} databases → {out_path}")


# ── train.json / dev.json generation ──────────────────────────────────────

def _hf_to_spider_format(example: dict) -> dict:
    return {
        "db_id":   example["db_id"],
        "query":   example["query"],
        "question": example["question"],
        "query_toks":          example.get("query_toks", []),
        "query_toks_no_value": example.get("query_toks_no_value", []),
        "question_toks":       example.get("question_toks", []),
    }


def build_qa_json() -> None:
    ds = load_dataset("spider")

    known_dbs = {d.name for d in (SPIDER_DIR / "database").iterdir() if d.is_dir()}
    print(f"Known databases: {len(known_dbs)}")

    for split, hf_key in [("train", "train"), ("dev", "validation")]:
        rows = [_hf_to_spider_format(ex) for ex in ds[hf_key] if ex["db_id"] in known_dbs]
        out_path = SPIDER_DIR / f"{split}.json"
        out_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
        print(f"{split}.json: {len(rows)} examples → {out_path}")


if __name__ == "__main__":
    if not (SPIDER_DIR / "database").exists():
        print("ERROR: Run the DB build script first (CMspider shards → SQLite)")
        raise SystemExit(1)

    print("=== tables.json ===")
    build_tables_json()

    print("\n=== train.json / dev.json ===")
    build_qa_json()

    print("\nDone. Spider directory ready at:", SPIDER_DIR)
