# text2sql

Natural language to SQL over a competition-platform database.  
A full-stack research project: schema design → data generation → retrieval-augmented generation → TUI tooling.

---

## Architecture

```text
User question
      │
      ▼
┌─────────────────────────────────────────────────┐
│                 LLM Service (FastAPI)            │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │            RAG Pipeline                  │    │
│  │  BM25 ──┐                               │    │
│  │         ├──► HybridRetriever            │    │
│  │  FAISS ─┘        │                      │    │
│  │             CrossEncoder reranker        │    │
│  │                  │                       │    │
│  │         tables + examples context        │    │
│  └──────────────────┼──────────────────────┘    │
│                     │                            │
│  ┌──────────────────▼──────────────────────┐    │
│  │         Knowledge Graph                  │    │
│  │   FK-path expansion (Dijkstra)           │    │
│  │   DDL enrichment → JOIN hints            │    │
│  └──────────────────┼──────────────────────┘    │
│                     │                            │
│              LLM (OpenRouter / Ollama)           │
│                     │                            │
└─────────────────────┼───────────────────────────┘
                      │ SQL
                      ▼
               PostgreSQL (Docker)
                      │
                      ▼
                  JSON result
```

---

## Stack

| Layer | Tech |
| --- | --- |
| Database | PostgreSQL 16 (Docker) |
| Embeddings | `intfloat/multilingual-e5-base` (sentence-transformers, MPS-accelerated) |
| Dense retrieval | FAISS `IndexFlatIP` |
| Sparse retrieval | BM25 (custom implementation) |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Graph traversal | NetworkX (Dijkstra) |
| LLM | OpenRouter API / Ollama (local) |
| Service | FastAPI + uvicorn |
| TUI | Textual |
| Data generation | asyncpg + Faker |

---

## Project structure

```text
text2sql/
├── infra/                  # Docker Compose + DB config
├── initdb/                 # SQL schema (DDL, constraints, indexes)
├── seed/                   # Async data generator
│   ├── inserter.py         # Generic batch inserter with dependency resolution
│   ├── seed_base/core/sub  # Seeding layers (users → teams → submissions)
│   └── seed_runner.py      # Entry point
├── llm/
│   ├── src/
│   │   ├── rag/            # Hybrid retriever pipeline
│   │   │   ├── faiss_retriever.py
│   │   │   ├── bm25_retriever.py
│   │   │   ├── hybrid_retriever.py
│   │   │   ├── cross_encoder_scorer.py
│   │   │   └── ddl_enricher.py
│   │   ├── graph.py        # FK knowledge graph + Dijkstra expansion
│   │   ├── llm.py          # LLM client (OpenRouter)
│   │   ├── llm_service.py  # FastAPI service
│   │   ├── benchmark.py    # Automated evaluation runner
│   │   └── judje.py        # LLM-based SQL judge
│   ├── docs/
│   │   ├── rag.yaml        # Table descriptions + retrieval examples
│   │   └── graph.yaml      # FK graph definition + algorithm config
│   └── benchmark_cases.json
├── cli/                    # Textual TUI (seeder + LLM query)
└── main.py                 # TUI entry point
```

---

## Setup

### 1. Environment

Copy and fill `.env`:

```env
POSTGRES_USER=competition_user
POSTGRES_PASSWORD=competition_pass
POSTGRES_DB=competition_db
DB_HOST=127.0.0.1
DB_PORT=5436

OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=qwen/qwen-2.5-coder-32b-instruct
```

### 2. Database

```bash
make up      # start PostgreSQL in Docker
make seed    # populate with synthetic data (~3 000 rows across all tables)
```

To reset:

```bash
make reset
```

### 3. LLM service

Requires `ollama` running locally or a valid `OPENROUTER_API_KEY`.

```bash
cd llm
make serve-api   # uvicorn on :8000
```

With a local Ollama model:

```bash
make serve-llama   # start ollama daemon
make serve-api
```

### 4. TUI

```bash
make cli           # or: python3 main.py
```

The TUI provides:

- layered data seeding with configurable counts
- table row inspection
- LLM query interface (sends to `http://localhost:8000/generate`)

### 5. CLI client (lightweight alternative to TUI)

```bash
cd llm
python3 -m src.cli
```

---

## Retrieval pipeline

The RAG pipeline operates over two slot types — `tables` and `examples` — loaded from `llm/docs/rag.yaml`.

Each query goes through:

1. **BM25** — keyword overlap over tokenized docs (Unicode-aware, custom IDF)
2. **FAISS** — cosine similarity over E5 embeddings
3. **Cross-encoder reranking** — `ms-marco-MiniLM-L-6-v2` scores all candidates jointly
4. **Minimum enforcement** — guarantees at least 4 table docs and 2 example docs in the final context
5. **Knowledge Graph expansion** — adds FK-adjacent tables and injects Dijkstra-computed JOIN path as a hint

The final context passed to the LLM contains:

- DDL with inline column annotations
- FK-path hint (`Tables: A → B → C` + JOIN clauses)
- Up to 3 similar example queries

---

## Benchmark

Evaluation uses an LLM-based judge that scores generated SQL against the user's intent (not exact string match). Scoring rubric: 0.95–1.0 = semantically equivalent, 0.70–0.84 = partial, <0.40 = wrong.

```text
Model: qwen2.5-coder:14b (local, Ollama)
Cases: 12
──────────────────────────────
Passed:    8 / 12  (66.7 %)
Avg score: 0.918
Avg time:  80 s / query
```

To run:

```bash
cd llm
python3 -m src.benchmark --input benchmark_cases.json --output results.json
```

---

## Reports

- [`reports/report.pdf`](reports/report.pdf) — academic paper: problem formulation, RAG/CoT/LLM-as-Judge methodology, implementation, benchmark analysis
- [`reports/summary.pdf`](reports/summary.pdf) — technical overview with architecture diagram, component rationale, and development directions
