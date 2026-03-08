from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import faiss
import numpy as np

from .embeddings import EmbeddingModel
from .utils import Logger, YamlReader

# ─── retrieval constants ──────────────────────────────────────────────────────

_WEIGHTS    = {"tables": 0.6, "examples": 0.8}
_CANDS      = {"tables": 12,  "examples": 8}
_MINIMUMS   = {"tables": 4,   "examples": 2}
_KIND       = {"tables": "table", "examples": "example"}
_MIN_COSINE = 0.12  # discard candidates below this raw cosine similarity

# _score carries the raw cosine through the whole pipeline so logs always show it.
_DOC_FIELDS = ("kind", "text", "context_text", "table", "example_id", "_score")

_NOTE_STOP = {"уникальный идентификатор", "первичный ключ", "FK на", "fk на"}

# ─── module-level helpers ─────────────────────────────────────────────────────

def _col_note(retrieval_text: str) -> str:
    """Short human-readable column annotation for DDL enrichment."""
    if not retrieval_text:
        return ""
    rt = retrieval_text.strip().lower()
    if any(rt.startswith(stop) for stop in _NOTE_STOP):
        return ""
    note = retrieval_text.split(",")[0].split(".")[0].strip()
    return note[:40] if len(note) > 3 else ""


def _doc_key(it: Dict) -> str:
    """Stable deduplication key across the merge/enforce pipeline."""
    return f"{it['kind']}:{it.get('table')}:{it.get('example_id')}"


def _copy_doc(it: Dict) -> Dict:
    """Copy only the canonical output fields from a raw search hit."""
    return {f: it.get(f) for f in _DOC_FIELDS}

# ─── DDL enrichment (pure functions, no class dependency) ─────────────────────

def _split_cols(cols_str: str) -> List[str]:
    """Bracket-aware comma split — keeps enum/set literals like {a,b} intact."""
    parts, depth, buf = [], 0, []
    for ch in cols_str:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return parts


def _enrich_ddl(context_text: str, columns_cfg: Dict[str, Any]) -> str:
    """Append inline column notes to a DDL string like `table(col TYPE ...)`."""
    if not columns_cfg or not context_text:
        return context_text
    paren = context_text.find("(")
    if paren == -1:
        return context_text
    table_part = context_text[:paren]
    cols_str   = context_text[paren + 1:].rstrip(")")
    enriched: List[str] = []
    for segment in _split_cols(cols_str):
        segment  = segment.strip()
        col_name = segment.split()[0] if segment else ""
        note     = _col_note(columns_cfg.get(col_name, {}).get("retrieval_text", ""))
        enriched.append(f"{segment} -- {note}" if note else segment)
    return f"{table_part}({', '.join(enriched)})"

# ─── RAG ──────────────────────────────────────────────────────────────────────

class RAG:
    def __init__(self, embed_model: EmbeddingModel) -> None:
        self.embed   = embed_model
        self.dim     = int(self.embed.dim)
        self._idx:   Dict[str, faiss.IndexFlatIP]    = {s: faiss.IndexFlatIP(self.dim) for s in _WEIGHTS}
        self._docs:  Dict[str, List[Dict[str, Any]]] = {s: [] for s in _WEIGHTS}
        self._logger = Logger.get_logger("src.rag", filename="rag.log")

    # ── index building ────────────────────────────────────────────────────────

    def build_from_yaml(self, path: Union[str, Path, None] = None) -> None:
        entries = YamlReader.load(path)
        self._logger.info("Building RAG from yaml: %d tables", len(entries))
        ex_id = 0
        for entry in entries:
            tbl = entry["table"]
            if rt := entry.get("retrieval_text", ""):
                ctx = _enrich_ddl(entry.get("context_text", ""), entry.get("columns", {}))
                self._add("tables", rt, {"table": tbl, "context_text": ctx})
            for ex in entry.get("examples", []):
                if not isinstance(ex, dict):
                    continue
                q = (ex.get("query") or "").strip()
                a = (ex.get("answer") or "").strip()
                if q:
                    self._add("examples", f"{q}\nSQL: {a}" if a else q,
                              {"table": tbl, "example_id": ex_id})
                    ex_id += 1
        self._logger.info("Index sizes: tables=%d examples=%d",
                          self._idx["tables"].ntotal, self._idx["examples"].ntotal)

    def _embed(self, text: str, is_query: bool = False) -> np.ndarray:
        v = np.array(self.embed.embed(text, is_query=is_query), dtype="float32").reshape(1, -1)
        faiss.normalize_L2(v)
        return v

    def _add(self, slot: str, text: str, meta: Dict[str, Any]) -> None:
        self._idx[slot].add(self._embed(text))
        self._docs[slot].append({"text": text, "kind": _KIND[slot], **meta})

    # ── search pipeline ───────────────────────────────────────────────────────

    def _search(self, slot: str, qv: np.ndarray) -> List[Dict]:
        idx = self._idx[slot]
        if idx.ntotal == 0:
            return []
        D, I = idx.search(qv, min(_CANDS[slot], idx.ntotal))
        return [
            {**self._docs[slot][i], "_score": float(score)}
            for score, i in zip(D[0], I[0])
            if i != -1 and score >= _MIN_COSINE
        ]

    @staticmethod
    def _normalise(items: List[Dict]) -> List[Dict]:
        """Max-normalisation: hi → 1.0, others proportional. Preserves relative gaps."""
        if not items:
            return items
        hi = max(it["_score"] for it in items)
        for it in items:
            it["norm_score"] = float(it["_score"] / hi) if hi > 0 else 0.0
        return items

    def _merge(self, per_slot: Dict[str, List[Dict]]) -> List[Dict]:
        """Combine slots into one ranked list, keeping the highest weighted score per doc."""
        seen: Dict[str, Dict] = {}
        for slot, items in per_slot.items():
            w = _WEIGHTS[slot]
            for it in items:
                key   = _doc_key(it)
                score = w * it.get("norm_score", 0.0)
                if key not in seen or score > seen[key]["score"]:
                    seen[key]          = _copy_doc(it)
                    seen[key]["score"] = score
        return sorted(seen.values(), key=lambda x: x["score"], reverse=True)

    def _enforce_minimums(self, results: List[Dict],
                           per_slot: Dict[str, List[Dict]]) -> List[Dict]:
        """Guarantee _MINIMUMS[slot] items per kind by pulling from raw candidate lists."""
        present = {_doc_key(r) for r in results}
        counts  = Counter(r["kind"] for r in results)
        for slot, minimum in _MINIMUMS.items():
            kind    = _KIND[slot]
            deficit = minimum - counts.get(kind, 0)
            for it in per_slot.get(slot, []):
                if deficit <= 0:
                    break
                key = _doc_key(it)
                if key in present:
                    continue
                entry          = _copy_doc(it)
                entry["score"] = _WEIGHTS[slot] * it.get("norm_score", 0.0)
                results.append(entry)
                present.add(key)
                deficit -= 1
        return results

    # ── public API ────────────────────────────────────────────────────────────

    def retrieve(self, query: str, k: int = 12) -> Dict[str, Any]:
        self._logger.info("Retrieve query=%r k=%d", query, k)
        qv       = self._embed(query, is_query=True)
        per_slot = {slot: self._normalise(self._search(slot, qv)) for slot in _WEIGHTS}
        results  = self._merge(per_slot)
        results = sorted(results, key=lambda x: x["score"], reverse=True)[:k]
        results = self._enforce_minimums(results, per_slot)

        counts = Counter(r["kind"] for r in results)
        self._logger.info("Retrieved %d docs — tables=%d examples=%d",
                          len(results), counts.get("table", 0), counts.get("example", 0))
        self._log_results(results)
        return {"results": results, "per_index": per_slot}

    def context_for(self, question: str, k: int = 12) -> Tuple[Dict[str, str], List[str]]:
        tables:   Dict[str, str] = {}
        examples: List[str]      = []
        for it in self.retrieve(question, k=k)["results"]:
            kind = it.get("kind", "")
            if kind == "table":
                tname = it.get("table") or ""
                if tname and tname not in tables:
                    tables[tname] = it.get("context_text") or it.get("text", "")
            elif kind == "example":
                examples.append(it.get("text", ""))
        return tables, examples

    def ddl_lookup(self) -> Dict[str, str]:
        """Full DDL map for every indexed table (used by graph.enrich)."""
        return {
            doc["table"]: doc.get("context_text") or doc.get("text", "")
            for doc in self._docs["tables"]
            if doc.get("table")
        }

    # ── logging ───────────────────────────────────────────────────────────────

    def _log_results(self, results: List[Dict]) -> None:
        lines = [f"{'#' * 6} RAG top {len(results)} {'#' * 6}"]
        for i, r in enumerate(results, 1):
            text = (r.get("text") or "").replace("\n", " ")[:100]
            lines.append(
                f"  {i:>2}. [{r['kind']:<7}] {r.get('table', '—'):<30}"
                f" score={r.get('score', 0):.4f}  cosine={r.get('_score', 0):.4f}  \"{text}\""
            )
        lines.append("#" * 36)
        self._logger.info("\n".join(lines))
