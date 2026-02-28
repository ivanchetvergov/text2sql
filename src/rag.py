from embeddings import EmbeddingModel
import faiss
import numpy as np
from scipy.special import softmax
from typing import List, Dict, Any, Optional
from logger import get_logger

_logger = get_logger("src.rag", filename="rag.log")

class RAG:
    def __init__(self, embed_model: EmbeddingModel):
        self.embed = embed_model
        self.dim = int(self.embed.dim)

        self.index_tables = faiss.IndexFlatIP(self.dim)
        self.index_columns = faiss.IndexFlatIP(self.dim)
        self.index_examples = faiss.IndexFlatIP(self.dim)

        self.docs_tables: List[Dict[str, Any]] = []
        self.docs_columns: List[Dict[str, Any]] = []
        self.docs_examples: List[Dict[str, Any]] = []

        self.weights = {"tables": 0.8, "columns": 1.0, "examples": 1.2}
        self.softmax_T = 1.0
        _logger.info("RAG initialized (dim=%d)", self.dim)

    def _embed_vector(self, text: str) -> np.ndarray:
        v = np.array(self.embed.embed(text), dtype="float32")
        if v.ndim == 1:
            v = v.reshape(1, -1)
        faiss.normalize_L2(v)
        return v

    def _stable_softmax(self, scores: np.ndarray) -> np.ndarray:
        raise NotImplementedError("Use scipy.special.softmax via retrieve()")

    def _add(self, index: faiss.IndexFlatIP,
                   docs: List[Dict[str, Any]],
                   text: str,
                   meta: Dict[str, Any]) -> None:
        vec = self._embed_vector(text)
        index.add(vec)
        entry = {"text": text, **meta}
        docs.append(entry)
        _logger.debug("Added doc kind=%s table=%s index_size=%d", meta.get("kind"), meta.get("table"), index.ntotal)

    def add_table(self, text: str, table: Optional[str] = None) -> None:
        self._add(self.index_tables, self.docs_tables, text, {"kind": "table", "table": table})

    def add_column(self, text: str, table: Optional[str] = None, column: Optional[str] = None) -> None:
        self._add(self.index_columns, self.docs_columns, text, {"kind": "column", "table": table, "column": column})

    def add_example(self, text: str, table: Optional[str] = None, example_id: Optional[int] = None, role: str = "example") -> None:
        self._add(self.index_examples, self.docs_examples, text, {"kind": "example", "table": table, "example_id": example_id, "role": role})

    def build_from_schema(self, entries: List[Dict[str, Any]]) -> None:
        _logger.info("Building RAG from schema with %d entries", len(entries))
        names = ", ".join(e.get("table", "") for e in entries)
        if names:
            self.add_table(f"Schema tables: {names}")

        example_counter = 0
        for entry in entries:
            tbl = entry.get("table")
            desc = entry.get("description", "")
            if tbl:
                self.add_table(f"{tbl}: {desc}", table=tbl)

            attrs = entry.get("attributes", []) or []
            if attrs:
                cols = ", ".join(attrs)
                self.add_column(f"{tbl}.columns: {cols}", table=tbl)
                for a in attrs:
                    self.add_column(f"{tbl}.{a}", table=tbl, column=a)

            for ex in entry.get("examples", []):
                if isinstance(ex, dict):
                    q = ex.get("query", "")
                    a = ex.get("answer", "")
                    if q:
                        self.add_example(q, table=tbl, example_id=example_counter, role="query")
                    if a:
                        self.add_example(a, table=tbl, example_id=example_counter, role="answer")
                    combined = (q + " \nSQL: " + a).strip()
                    if combined:
                        self.add_example(combined, table=tbl, example_id=example_counter, role="example")
                    example_counter += 1
                else:
                    s = str(ex)
                    self.add_example(s, table=tbl, example_id=example_counter, role="example")
                    example_counter += 1

    def _search_index(self, index: faiss.IndexFlatIP, docs: List[Dict[str, Any]], qv: np.ndarray, k: int):
        if index.ntotal == 0:
            _logger.debug("Search on empty index (k=%d)", k)
            return []
        D, I = index.search(qv, k)
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx == -1:
                continue
            meta = docs[idx].copy()
            meta["score"] = float(score)
            meta["index_id"] = int(idx)
            results.append(meta)
        _logger.debug("Search returned %d results (requested k=%d)", len(results), k)
        return results

    def retrieve(self, query: str, k: int = 5, table_filter: Optional[str] = None) -> Dict[str, Any]:
        _logger.info("Retrieving: query=%s k=%d table_filter=%s", query, k, table_filter)
        qv = self._embed_vector(query)

        idx_results = {
            "tables": self._search_index(self.index_tables, self.docs_tables, qv, k - 2),
            "columns": self._search_index(self.index_columns, self.docs_columns, qv, k),
            "examples": self._search_index(self.index_examples, self.docs_examples, qv, k),
        }

        normed: Dict[str, List[Dict[str, Any]]] = {}
        for name, items in idx_results.items():
            if not items:
                normed[name] = []
                continue
            scores = np.array([it["score"] for it in items], dtype="float32")
            T = max(float(self.softmax_T), 1e-6)
            probs = softmax(scores.astype("float64") / T)
            if not np.isfinite(probs).all() or float(probs.sum()) == 0.0:
                probs = np.ones_like(scores, dtype="float32") / float(len(scores))
            probs = probs.astype("float32")
            for it, p in zip(items, probs):
                it["norm_score"] = float(p)
            normed[name] = items

        fused: Dict[str, Dict[str, Any]] = {}
        for name, items in normed.items():
            w = float(self.weights.get(name, 1.0))
            for it in items:
                if table_filter and it.get("table") and it.get("table") != table_filter:
                    continue
                key = f"{name}:{it.get('index_id')}:{it.get('role', '')}:{it.get('example_id', '')}"
                score = w * it.get("norm_score", 0.0)
                if key in fused:
                    fused[key]["score"] += score
                else:
                    fused[key] = {"text": it.get("text"),
                                  "kind": it.get("kind"),
                                  "table": it.get("table"),
                                  "role": it.get("role"),
                                  "example_id": it.get("example_id"),
                                  "score": score
                                  }

        results = sorted(fused.values(), key=lambda x: x["score"], reverse=True)[:k]
        _logger.info("Returning %d fused results", len(results))
        return {"results": results, "per_index": idx_results}


