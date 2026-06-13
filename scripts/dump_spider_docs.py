"""Pre-build Spider schema docs for fast RAG loading.

Reads Spider tables.json + SQLite databases, generates enriched RAG entries
(with LLM-annotated column/table descriptions and sampled values), and saves
them to docs/spider/{db_id}.json. SpiderLoader will load from these files
instead of re-processing tables.json on every benchmark run.

Usage:
    # Enrich one database (runs LLM, ~30s)
    python -m scripts.dump_spider_docs --spider data/spider --db concert_singer --enrich

    # Enrich all 166 databases (long, use --limit to test first)
    python -m scripts.dump_spider_docs --spider data/spider --enrich --limit 5

    # Dump without LLM enrichment (fast, just caches schema)
    python -m scripts.dump_spider_docs --spider data/spider
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# make sure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.spider import SpiderLoader
from src.retrieval.enrichment import SchemaEnricher, sample_values
from src.utils import load_env


def _build_ddl(entry: dict) -> str:
    ctx = entry.get("context_text", "")
    if "(" in ctx:
        tbl, rest = ctx.split("(", 1)
        cols = rest.rstrip(")")
        lines = [f"CREATE TABLE {tbl.strip()} ("]
        for part in cols.split(","):
            lines.append(f"    {part.strip()},")
        if lines[-1].endswith(","):
            lines[-1] = lines[-1][:-1]
        lines.append(")")
        return "\n".join(lines)
    return ctx


def _apply_enrichment(entry: dict, enrichment: dict) -> dict:
    entry = dict(entry)
    entry["description"] = enrichment.get("table_description", "")
    col_descriptions: dict[str, str] = enrichment.get("columns", {})

    enriched_cols = dict(entry.get("columns", {}))
    for col_name, desc in col_descriptions.items():
        existing = enriched_cols.get(col_name, {})
        enriched_cols[col_name] = {
            **existing,
            "description":    desc,
            "retrieval_text": desc,
        }
    entry["columns"] = enriched_cols
    return entry


def dump_db(
    db_id: str,
    loader: SpiderLoader,
    spider_root: Path,
    enricher: SchemaEnricher | None,
) -> dict:
    rag_entries, graph_data = loader.schema_for(db_id, attach_examples=False)
    db_path = spider_root / "database" / db_id / f"{db_id}.db"

    final_entries = []
    for entry in rag_entries:
        table = entry["table"]

        samples: dict = {}
        if db_path.exists():
            col_names = [
                c.split()[0]
                for c in entry.get("context_text", "").split("(", 1)[-1].rstrip(")").split(",")
                if c.strip()
            ]
            samples = sample_values(db_path, table, col_names, n=5)
        entry["samples"] = samples

        if enricher is not None:
            ddl = _build_ddl(entry)
            enrichment = enricher.enrich_table(table, ddl, samples)
            if enrichment.get("_error"):
                print(f"    [WARN] {db_id}.{table}: {enrichment['_error']}")
            entry = _apply_enrichment(entry, enrichment)

        final_entries.append(entry)

    return {
        "db_id":    db_id,
        "enriched": enricher is not None,
        "entries":  final_entries,
    }


def main() -> None:
    load_env()

    parser = argparse.ArgumentParser(description="Pre-build Spider schema docs")
    parser.add_argument("--spider",     required=True,  help="Path to Spider root dir")
    parser.add_argument("--db",         default=None,   help="Single db_id to process (default: all)")
    parser.add_argument("--enrich",     action="store_true", help="Run LLM enrichment")
    project_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--output-dir", default=str(project_root / "docs" / "spider"), help="Output directory")
    parser.add_argument("--limit",      type=int, default=None, help="Max number of DBs to process")
    args = parser.parse_args()

    spider_root = Path(args.spider)
    output_dir  = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    loader = SpiderLoader(spider_root)
    db_ids = [args.db] if args.db else loader.all_db_ids()
    if args.limit:
        db_ids = db_ids[:args.limit]

    enricher: SchemaEnricher | None = None
    if args.enrich:
        from src.generation.llm import LLM
        llm = LLM(
            url=os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions"),
            model_name=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free"),
            check=False,
        )
        enricher = SchemaEnricher(llm)
        print(f"LLM enrichment ON — model: {llm.model_name}")

    print(f"Processing {len(db_ids)} databases → {output_dir}\n")

    ok, failed = 0, 0
    for i, db_id in enumerate(db_ids, 1):
        out_path = output_dir / f"{db_id}.json"
        t0 = time.perf_counter()
        try:
            doc = dump_db(db_id, loader, spider_root, enricher)
            out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
            model = f" [{enricher._llm.last_used_model}]" if enricher else ""
            elapsed = round(time.perf_counter() - t0, 1)
            print(f"  [{i:>3}/{len(db_ids)}] {db_id:<35} {len(doc['entries'])} tables  {elapsed}s{model}")
            ok += 1
        except Exception as exc:
            print(f"  [{i:>3}/{len(db_ids)}] {db_id:<35} FAILED: {exc}")
            failed += 1

    print(f"\nDone: {ok} ok, {failed} failed")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
