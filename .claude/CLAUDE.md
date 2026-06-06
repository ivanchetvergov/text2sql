# text2sql

Research system for natural language to SQL translation using RAG + Knowledge Graph + LLM.
Academic project (2nd year bachelor, SPbPU, group 5130201/30003). Supervisor: Попов С.Г.

## Goal

Evaluate whether augmenting an LLM with hybrid RAG retrieval and a FK-aware Knowledge Graph
improves Text-to-SQL accuracy on the Spider benchmark. Primary metric: execution accuracy (EX).

## Architecture

```
Question
   │
   ▼
Pipeline.generate()
   ├─ RAG.context_for()          dense (FAISS) + sparse (BM25) + cross-encoder rerank
   │   └─ returns tables dict + few-shot examples
   ├─ KnowledgeGraph.enrich()    Dijkstra over FK graph → join path hint
   │
   ├─ LLM.call()                 OpenRouter API (Qwen2.5-Coder or fallback)
   │
   └─ Judge.evaluate()           LLM-as-Judge → if rejected, one correction attempt
```

## Project Structure

```
text2sql/
  src/
    llm.py          HTTP client for OpenRouter-compatible APIs
    pipeline.py     Orchestrator: RAG + KG + generation + judge refinement
    judge.py        LLM-as-Judge (returns JSON: valid, score, error)
    prompts.py      Prompt strings (English, dialect-agnostic)
    graph.py        FK Knowledge Graph (networkx, Dijkstra, weighted edges)
    spider.py       Spider dataset adapter (tables.json → RAG entries + graph)
    benchmark.py    Benchmark runner; supports custom JSON and Spider datasets
    llm_service.py  FastAPI service: /generate, /health; executes SQL on PostgreSQL
    cli.py          CLI client for the FastAPI service
    utils.py        YamlReader, GraphReader, Logger
    rag/
      __init__.py   exports RAG, EmbeddingModel
      index.py      RAG class: indexes entries, retrieves context, enforces slot minimums
      embeddings.py SentenceTransformer wrapper (multilingual-e5-base, MPS-accelerated)
      faiss_retriever.py    Dense retrieval (IndexFlatIP)
      bm25_retriever.py     Sparse keyword retrieval
      hybrid_retriever.py   Merges dense + sparse, reranks via cross-encoder
      cross_encoder_scorer.py  ms-marco-MiniLM-L-6-v2 (lexical fallback if unavailable)
      ddl_enricher.py       Adds column notes to DDL from YAML config
      text_utils.py         Tokenization (Unicode + Cyrillic), doc dedup
      constants.py          CANDIDATES_PER_SLOT, MINIMUMS_PER_SLOT
  docs/
    rag.yaml        Hand-crafted RAG entries for the custom competition DB schema
    graph.yaml      Hand-crafted FK graph for the custom competition DB schema
  logs/             Runtime logs (git-ignored)
  results/          Benchmark output JSON files (git-ignored)
  reports/          Academic papers (PDF)
  Makefile
  README.md
```

## Running

```bash
# Start FastAPI service
make serve

# Run Spider benchmark on a specific database
make bench ARGS="--spider /path/to/spider --db concert_singer --output results.json"

# Run on custom JSON cases
make bench ARGS="--input benchmark_cases.json --output results.json"
```

## Key Design Decisions

**RAG dual-slot** — separate FAISS/BM25 indexes for `tables` (schema DDL) and `examples`
(Q&A pairs). Minimum coverage per slot is enforced after reranking.

**FK graph edge weights** — `w(u,v) = 1.0 + δ_cardinality + max(0, hub_avg - 1) * hub_step_cost`.
Higher cardinality cost penalizes one-to-many joins; hub score penalizes joining through
high-degree tables (avoids unnecessary fan-outs).

**Judge-driven correction** — after generating SQL, `Pipeline._refine()` runs one judge pass.
If rejected, it retries with the error message injected into the prompt (temperature=0).

**Spider adapter** — `SpiderLoader` builds RAG entries from `tables.json` using natural-language
column names (`column_names` field, not `column_names_original`). Training examples from
`train_spider.json` are attached per-table using FROM-clause heuristic.

## Environment Variables

```
OPENROUTER_API_KEY      required
OPENROUTER_URL          default: https://openrouter.ai/api/v1/chat/completions
OPENROUTER_MODEL        default: qwen/qwen-2.5-coder-32b-instruct
OPENROUTER_FALLBACK_MODELS  comma-separated fallback model IDs
RAG_TABLE_LIMIT         max tables after RAG retrieval (default: 6)
RAG_FINAL_TABLE_LIMIT   max tables after KG enrichment (default: 6)
LLM_RESULT_LIMIT        max rows returned by service (default: 20)
POSTGRES_USER/PASSWORD/DB/HOST/PORT  for llm_service SQL execution
```

## Status

- Spider benchmark infrastructure: complete
- EX metric via SQLite: complete
- English prompts (dialect-agnostic): complete
- Ablation study (with/without KG): pending
- Schema enrichment via LLM preprocessing: planned
