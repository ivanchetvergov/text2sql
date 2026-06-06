"""
Benchmark runner for text2sql.

Usage:
    python -m src.benchmark --input cases.json --output results.json
    python -m src.benchmark --spider /path/to/spider --db concert_singer --output results.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .retrieval import EmbeddingModel, KnowledgeGraph, RAG
from .generation import Judge, LLM, Pipeline
from .utils import Logger

_logger = Logger.get_logger("src.benchmark", filename="benchmark.log")


# ─── pipeline builders ────────────────────────────────────────────────────────

def _build_pipeline(url: str, timeout: float) -> Pipeline:
    rag = RAG(EmbeddingModel())
    try:
        rag.build_from_yaml()
    except Exception as exc:
        _logger.exception("Failed to build RAG: %s", exc)
        raise

    kg: Optional[KnowledgeGraph] = None
    try:
        kg = KnowledgeGraph().load_from_yaml()
    except Exception as exc:
        _logger.warning("KnowledgeGraph unavailable: %s", exc)

    return Pipeline(llm=LLM(url=url, timeout=timeout), rag=rag, kg=kg)


def _build_spider_pipeline(url: str, timeout: float, loader: Any, db_id: str) -> Pipeline:
    rag_entries, graph_data = loader.schema_for(db_id)

    rag = RAG(EmbeddingModel())
    rag.build_from_entries(rag_entries)

    kg: Optional[KnowledgeGraph] = None
    try:
        kg = KnowledgeGraph().load_from_dict(graph_data)
    except Exception as exc:
        _logger.warning("KnowledgeGraph build failed: %s", exc)

    return Pipeline(llm=LLM(url=url, timeout=timeout), rag=rag, kg=kg)


# ─── SQLite execution accuracy ────────────────────────────────────────────────

def _exec_sqlite(sql: str, db_path: str) -> Optional[List[tuple]]:
    try:
        with sqlite3.connect(db_path) as conn:
            return conn.execute(sql).fetchall()
    except Exception:
        return None


def _results_match(a: Optional[List[tuple]], b: Optional[List[tuple]]) -> bool:
    return a is not None and b is not None and set(map(tuple, a)) == set(map(tuple, b))


# ─── single case runner ───────────────────────────────────────────────────────

def _run_case(
    pipeline: Pipeline,
    judge: Judge,
    case: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    question     = case["question"]
    expected_sql = case.get("expected_sql", "")

    t0 = time.perf_counter()
    generated_sql  = ""
    generate_error: Optional[str] = None
    verdict: Dict[str, Any] = {}

    try:
        generated_sql = pipeline.generate(question)
    except Exception as exc:
        generate_error = str(exc)
        _logger.error("generate() failed for %s: %s", case.get("id"), exc)

    duration_s = round(time.perf_counter() - t0, 2)

    if generated_sql and not generate_error:
        try:
            verdict = judge.evaluate(question, generated_sql)
        except Exception as exc:
            _logger.warning("judge.evaluate() failed for %s: %s", case.get("id"), exc)
            verdict = {"valid": False, "score": 0.0, "error": str(exc), "comments": ""}

    ex: Optional[bool] = None
    if db_path and generated_sql and expected_sql and not generate_error:
        ex = _results_match(
            _exec_sqlite(generated_sql, db_path),
            _exec_sqlite(expected_sql,  db_path),
        )

    status = "pass" if (verdict.get("valid") and not generate_error) else ("error" if generate_error else "fail")

    return {
        "id":            case.get("id", ""),
        "question":      question,
        "expected_sql":  expected_sql,
        "generated_sql": generated_sql,
        "ex":            ex,
        "judge": {
            "valid":    verdict.get("valid",    False),
            "score":    verdict.get("score",    0.0),
            "error":    verdict.get("error",    ""),
            "comments": verdict.get("comments", ""),
        },
        "status":     status,
        "duration_s": duration_s,
        "error":      generate_error,
    }


# ─── aggregate output ─────────────────────────────────────────────────────────

def _build_output(results: List[Dict[str, Any]], model_name: str, label: str) -> Dict[str, Any]:
    total   = len(results)
    passed  = sum(1 for r in results if r["status"] == "pass")
    failed  = sum(1 for r in results if r["status"] == "fail")
    errors  = sum(1 for r in results if r["status"] == "error")
    scores  = [r["judge"]["score"] for r in results if r["judge"]["score"] > 0]
    durs    = [r["duration_s"] for r in results]
    ex_vals = [r["ex"] for r in results if r.get("ex") is not None]

    return {
        "meta": {
            "run_at":      datetime.now(timezone.utc).isoformat(),
            "model":       model_name,
            "input_file":  label,
            "total_cases": total,
        },
        "summary": {
            "total":        total,
            "passed":       passed,
            "failed":       failed,
            "errors":       errors,
            "pass_rate":    round(passed / total, 4)           if total      else 0.0,
            "avg_score":    round(sum(scores) / len(scores), 4) if scores    else 0.0,
            "ex_accuracy":  round(sum(ex_vals) / len(ex_vals), 4) if ex_vals else None,
            "avg_duration_s": round(sum(durs) / len(durs), 2)  if durs      else 0.0,
        },
        "results": results,
    }


# ─── shared runner ────────────────────────────────────────────────────────────

def _run_benchmark(
    cases: List[Dict[str, Any]],
    pipeline: Pipeline,
    judge: Judge,
    output_path: str,
    label: str,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for i, case in enumerate(cases, 1):
        cid = case.get("id", f"#{i}")
        print(f"[{i}/{len(cases)}] {cid}: {case['question'][:70]}", end="  ", flush=True)
        result = _run_case(pipeline, judge, case, db_path=db_path)
        icon   = "✓" if result["status"] == "pass" else ("!" if result["status"] == "error" else "✗")
        ex_tag = f"  ex={'✓' if result['ex'] else '✗'}" if result.get("ex") is not None else ""
        print(f"{icon}  score={result['judge']['score']:.2f}{ex_tag}  {result['duration_s']}s")
        results.append(result)

    output = _build_output(results, pipeline.llm.model_name, label)
    Path(output_path).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    s = output["summary"]
    ex_line = f"  ex_acc={s['ex_accuracy']:.0%}" if s.get("ex_accuracy") is not None else ""
    print(
        f"\nDone — {s['passed']}/{s['total']} passed"
        f"  pass_rate={s['pass_rate']:.0%}"
        f"  avg_score={s['avg_score']:.2f}"
        f"{ex_line}  avg_time={s['avg_duration_s']}s"
    )
    print(f"Results saved → {output_path}")
    return output


# ─── entry points ─────────────────────────────────────────────────────────────

def run(
    input_path: str,
    output_path: str,
    url: str = "https://openrouter.ai/api/v1/chat/completions",
    timeout: float = 180.0,
) -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Input file must be a non-empty JSON array")

    print(f"Loaded {len(cases)} case(s) from {input_path}")
    print("Building pipeline…")
    pipeline = _build_pipeline(url, timeout)
    judge    = Judge(pipeline.llm)
    print("Pipeline ready.\n")
    return _run_benchmark(cases, pipeline, judge, output_path, input_path)


def run_spider(
    spider_root: str,
    db_id: str,
    output_path: str,
    split: str = "dev",
    url: str = "https://openrouter.ai/api/v1/chat/completions",
    timeout: float = 180.0,
) -> Dict[str, Any]:
    from .spider import SpiderLoader
    loader = SpiderLoader(spider_root)
    cases  = loader.questions_for(db_id, split=split)
    if not cases:
        raise ValueError(f"No questions found for db_id='{db_id}' in split='{split}'")

    db_path = str(Path(spider_root) / "database" / db_id / f"{db_id}.db")
    db_path = db_path if Path(db_path).exists() else None

    print(f"Loaded {len(cases)} case(s) for {db_id} ({split})")
    if db_path:
        print(f"SQLite EX enabled: {db_path}")
    print("Building pipeline…")
    pipeline = _build_spider_pipeline(url, timeout, loader, db_id)
    judge    = Judge(pipeline.llm)
    print("Pipeline ready.\n")
    return _run_benchmark(cases, pipeline, judge, output_path, f"spider:{db_id}:{split}", db_path=db_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="text2sql benchmark runner")
    parser.add_argument("--output",  required=True)
    parser.add_argument("--url",     default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--timeout", default=180.0, type=float)

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input",  help="JSON file with test cases")
    mode.add_argument("--spider", metavar="SPIDER_ROOT")

    parser.add_argument("--db",    metavar="DB_ID")
    parser.add_argument("--split", default="dev")
    args = parser.parse_args()

    try:
        if args.spider:
            if not args.db:
                parser.error("--db is required with --spider")
            run_spider(args.spider, args.db, args.output, args.split, args.url, args.timeout)
        else:
            run(args.input, args.output, args.url, args.timeout)
    except Exception as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
