"""
Benchmark runner for text2sql.

Usage:
    python -m src.benchmark --input cases.json --output results.json

Input file format (JSON array):
    [
      {
        "id": "q01",
        "question": "Сколько пользователей зарегистрировано?",
        "expected_sql": "SELECT COUNT(*) FROM \"user\" u"
      },
      ...
    ]

Output file: see _build_output() for the full schema.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .embeddings import EmbeddingModel
from .graph import KnowledgeGraph
from .judge import Judge
from .llm import LLM
from .rag import RAG
from .utils import Logger

_logger = Logger.get_logger("src.benchmark", filename="benchmark.log")


# ─── pipeline bootstrap ───────────────────────────────────────────────────────

def _build_pipeline(url: str, timeout: float) -> LLM:
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
        _logger.warning("KnowledgeGraph unavailable, continuing without it: %s", exc)

    return LLM(url=url, timeout=timeout, rag=rag, kg=kg)


def _build_spider_pipeline(url: str, timeout: float, spider_root: str, db_id: str) -> LLM:
    from .spider import SpiderLoader
    loader = SpiderLoader(spider_root)
    rag_entries, graph_data = loader.schema_for(db_id)

    rag = RAG(EmbeddingModel())
    rag.build_from_entries(rag_entries)

    kg: Optional[KnowledgeGraph] = None
    try:
        kg = KnowledgeGraph().load_from_dict(graph_data)
    except Exception as exc:
        _logger.warning("KnowledgeGraph build failed: %s", exc)

    return LLM(url=url, timeout=timeout, rag=rag, kg=kg)


# ─── single case runner ───────────────────────────────────────────────────────

def _run_case(llm: LLM, judge: Judge, case: Dict[str, Any]) -> Dict[str, Any]:
    question     = case["question"]
    expected_sql = case.get("expected_sql", "")

    t0 = time.perf_counter()
    generate_error: Optional[str] = None
    generated_sql  = ""
    verdict: Dict[str, Any] = {}

    try:
        generated_sql = llm.generate(question)
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

    passed = bool(verdict.get("valid")) and not generate_error
    status = "pass" if passed else ("error" if generate_error else "fail")

    return {
        "id":            case.get("id", ""),
        "question":      question,
        "expected_sql":  expected_sql,
        "generated_sql": generated_sql,
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


# ─── aggregate output builder ─────────────────────────────────────────────────

def _build_output(
    results: List[Dict[str, Any]],
    model_name: str,
    input_file: str,
) -> Dict[str, Any]:
    total    = len(results)
    passed   = sum(1 for r in results if r["status"] == "pass")
    failed   = sum(1 for r in results if r["status"] == "fail")
    errors   = sum(1 for r in results if r["status"] == "error")
    scores   = [r["judge"]["score"] for r in results if r["judge"]["score"] > 0]
    durs     = [r["duration_s"] for r in results]

    return {
        "meta": {
            "run_at":       datetime.now(timezone.utc).isoformat(),
            "model":        model_name,
            "input_file":   input_file,
            "total_cases":  total,
        },
        "summary": {
            "total":        total,
            "passed":       passed,
            "failed":       failed,
            "errors":       errors,
            "pass_rate":    round(passed / total, 4) if total else 0.0,
            "avg_score":    round(sum(scores) / len(scores), 4) if scores else 0.0,
            "avg_duration_s": round(sum(durs) / len(durs), 2) if durs else 0.0,
        },
        "results": results,
    }


# ─── main ─────────────────────────────────────────────────────────────────────

def run(
    input_path: str,
    output_path: str,
    url: str = "https://openrouter.ai/api/v1/chat/completions",
    timeout: float = 180.0,
) -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Input file must be a non-empty JSON array")

    print(f"Loaded {len(cases)} test case(s) from {input_path}")
    print("Building pipeline…")
    llm   = _build_pipeline(url, timeout)
    judge = Judge(llm)
    print("Pipeline ready.\n")

    results: List[Dict[str, Any]] = []
    for i, case in enumerate(cases, 1):
        cid = case.get("id", f"#{i}")
        print(f"[{i}/{len(cases)}] {cid}: {case['question'][:70]}", end="  ", flush=True)
        result = _run_case(llm, judge, case)
        icon = "✓" if result["status"] == "pass" else ("!" if result["status"] == "error" else "✗")
        score = result["judge"]["score"]
        print(f"{icon}  score={score:.2f}  {result['duration_s']}s")
        results.append(result)

    output = _build_output(results, llm.model_name, input_path)

    Path(output_path).write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    s = output["summary"]
    print(
        f"\nDone — {s['passed']}/{s['total']} passed"
        f"  pass_rate={s['pass_rate']:.0%}"
        f"  avg_score={s['avg_score']:.2f}"
        f"  avg_time={s['avg_duration_s']}s"
    )
    print(f"Results saved → {output_path}")
    return output


def run_spider(
    spider_root: str,
    db_id: str,
    output_path: str,
    split: str = "dev",
    url: str = "https://openrouter.ai/api/v1/chat/completions",
    timeout: float = 180.0,
) -> Dict[str, Any]:
    from .spider import SpiderLoader
    cases = SpiderLoader(spider_root).questions_for(db_id, split=split)
    if not cases:
        raise ValueError(f"No questions found for db_id='{db_id}' in split='{split}'")

    print(f"Loaded {len(cases)} case(s) for {db_id} ({split})")
    print("Building Spider pipeline…")
    llm   = _build_spider_pipeline(url, timeout, spider_root, db_id)
    judge = Judge(llm)
    print("Pipeline ready.\n")

    results: List[Dict[str, Any]] = []
    for i, case in enumerate(cases, 1):
        cid = case.get("id", f"#{i}")
        print(f"[{i}/{len(cases)}] {cid}: {case['question'][:70]}", end="  ", flush=True)
        result = _run_case(llm, judge, case)
        icon = "✓" if result["status"] == "pass" else ("!" if result["status"] == "error" else "✗")
        print(f"{icon}  score={result['judge']['score']:.2f}  {result['duration_s']}s")
        results.append(result)

    label = f"spider:{db_id}:{split}"
    output = _build_output(results, llm.model_name, label)
    Path(output_path).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    s = output["summary"]
    print(
        f"\nDone — {s['passed']}/{s['total']} passed"
        f"  pass_rate={s['pass_rate']:.0%}"
        f"  avg_score={s['avg_score']:.2f}"
        f"  avg_time={s['avg_duration_s']}s"
    )
    print(f"Results saved → {output_path}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="text2sql benchmark runner")
    parser.add_argument("--output",  required=True,  help="Path to write JSON results")
    parser.add_argument("--url",     default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--timeout", default=180.0, type=float)

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input",  help="JSON file with test cases (own schema)")
    mode.add_argument("--spider", metavar="SPIDER_ROOT", help="Path to Spider dataset root")

    parser.add_argument("--db",    metavar="DB_ID",  help="Spider database id (required with --spider)")
    parser.add_argument("--split", default="dev",    help="Spider split: train or dev (default: dev)")
    args = parser.parse_args()

    try:
        if args.spider:
            if not args.db:
                parser.error("--db is required when using --spider")
            run_spider(args.spider, args.db, args.output, args.split, args.url, args.timeout)
        else:
            run(args.input, args.output, args.url, args.timeout)
    except Exception as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
