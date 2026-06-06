from __future__ import annotations

from pathlib import Path
from typing import Any

from .bm25_retriever import BM25Retriever
from .constants import CANDIDATES_PER_SLOT, KIND_PER_SLOT, MINIMUMS_PER_SLOT
from .cross_encoder_scorer import MiniCrossEncoderScorer
from .ddl_enricher import enrich_ddl
from .embeddings import EmbeddingModel
from .faiss_retriever import FaissRetriever
from .hybrid_retriever import HybridRetriever
from .text_utils import copy_doc, count_kinds, doc_key
from ..utils import Logger, YamlReader


_TABLE_ALIASES = {
    "competition_config": "configuration",
    "file_artifact": "dataset_file",
    "leaderboard_row": "participation",
    "leaderboard_entry": "participation",
    "evaluation": "submission",
    "solution_code": "submission",
}


def _canonical_table(name: str) -> str:
    return _TABLE_ALIASES.get(name, name)


def _canonical_text(text: str) -> str:
    if not text:
        return text
    fixed = text
    fixed = fixed.replace("competition_config", "configuration")
    fixed = fixed.replace("file_artifact", "dataset_file")
    fixed = fixed.replace("leaderboard_row", "participation")
    fixed = fixed.replace("leaderboard_entry", "participation")
    fixed = fixed.replace("evaluation", "submission")
    fixed = fixed.replace("solution_code", "submission")
    fixed = fixed.replace("computed_at", "submitted_at")
    fixed = fixed.replace("evaluated_at", "submitted_at")
    fixed = fixed.replace("score", "best_score")
    return fixed


class RAG:
    def __init__(self, embed_model: EmbeddingModel) -> None:
        self._logger = Logger.get_logger("src.rag", filename="rag.log")
        dense = {slot: FaissRetriever(embed_model) for slot in KIND_PER_SLOT}
        bm25 = {slot: BM25Retriever() for slot in KIND_PER_SLOT}
        scorer = MiniCrossEncoderScorer(self._logger)
        self.retriever = HybridRetriever(dense=dense, bm25=bm25, scorer=scorer)
        self._docs: dict[str, list[dict[str, Any]]] = {slot: [] for slot in KIND_PER_SLOT}

    def build_from_entries(self, entries: list[dict]) -> None:
        self._logger.info("Building RAG from entries: %d tables", len(entries))
        example_id = 0
        for entry in entries:
            table_name = entry["table"]
            retrieval_text = entry.get("retrieval_text", "")
            if retrieval_text:
                context = enrich_ddl(entry.get("context_text", ""), entry.get("columns", {}))
                self._add("tables", retrieval_text, {"table": table_name, "context_text": context})
            for ex in entry.get("examples", []):
                if not isinstance(ex, dict):
                    continue
                question = (ex.get("query") or "").strip()
                answer = (ex.get("answer") or "").strip()
                if not question:
                    continue
                text = f"{question}\nSQL: {answer}" if answer else question
                self._add("examples", text, {"table": table_name, "example_id": example_id})
                example_id += 1

    def build_from_yaml(self, path: str | Path | None = None) -> None:
        raw = YamlReader.load(path)
        self._logger.info("Building RAG from yaml: %d tables", len(raw))
        canonical = []
        for e in raw:
            examples = [
                {**ex, "answer": _canonical_text((ex.get("answer") or "").strip())}
                for ex in (e.get("examples") or [])
                if isinstance(ex, dict)
            ]
            canonical.append({
                "table":          _canonical_table(e["table"]),
                "retrieval_text": _canonical_text(e.get("retrieval_text", "")),
                "context_text":   _canonical_text(e.get("context_text", "")),
                "columns":        e.get("columns") or {},
                "examples":       examples,
            })
        self.build_from_entries(canonical)

    def _add(self, slot: str, text: str, meta: dict[str, Any]) -> None:
        doc = {"text": text, "kind": KIND_PER_SLOT[slot], **meta}
        self.retriever.add(slot, doc)
        self._docs[slot].append(doc)

    def _merge(self, per_slot: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for items in per_slot.values():
            for item in items:
                key = doc_key(item)
                score = float(item.get("_score", 0.0))
                if key not in seen or score > float(seen[key].get("score", 0.0)):
                    seen[key] = copy_doc(item)
                    seen[key]["score"] = score
        return sorted(seen.values(), key=lambda x: float(x.get("score", 0.0)), reverse=True)

    def _enforce_minimums(
        self,
        results: list[dict[str, Any]],
        per_slot: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        present = {doc_key(item) for item in results}
        kind_counts = count_kinds(results)
        for slot, minimum in MINIMUMS_PER_SLOT.items():
            kind = KIND_PER_SLOT[slot]
            deficit = minimum - kind_counts.get(kind, 0)
            for item in per_slot.get(slot, []):
                if deficit <= 0:
                    break
                key = doc_key(item)
                if key in present:
                    continue
                entry = copy_doc(item)
                entry["score"] = float(item.get("_score", 0.0))
                results.append(entry)
                present.add(key)
                deficit -= 1
        return sorted(results, key=lambda x: float(x.get("score", 0.0)), reverse=True)

    def retrieve(self, query: str, k: int = 12) -> dict[str, Any]:
        per_slot = {
            slot: self.retriever.search(slot, query=query, top_k=CANDIDATES_PER_SLOT[slot])
            for slot in KIND_PER_SLOT
        }
        merged = self._merge(per_slot)
        merged = self._enforce_minimums(merged[:k], per_slot)
        self._log_results(merged)
        return {"results": merged, "per_index": per_slot}

    def context_for(self, question: str, k: int = 12) -> tuple[dict[str, str], list[str]]:
        tables: dict[str, str] = {}
        examples: list[str] = []
        for item in self.retrieve(question, k=k)["results"]:
            kind = item.get("kind", "")
            if kind == "table":
                table_name = item.get("table") or ""
                if table_name and table_name not in tables:
                    tables[table_name] = item.get("context_text") or item.get("text", "")
            elif kind == "example":
                examples.append(item.get("text", ""))
        return tables, examples

    def ddl_lookup(self) -> dict[str, str]:
        return {
            doc["table"]: doc.get("context_text") or doc.get("text", "")
            for doc in self._docs["tables"]
            if doc.get("table")
        }

    def _log_results(self, results: list[dict[str, Any]]) -> None:
        lines = [f"{'#' * 6} RAG top {len(results)} {'#' * 6}"]
        for i, item in enumerate(results, 1):
            text = (item.get("text") or "").replace("\n", " ")[:100]
            lines.append(
                f"  {i:>2}. [{item.get('kind', ''):<7}] {item.get('table', '—'):<30} "
                f"score={item.get('score', 0):.4f} \"{text}\""
            )
        lines.append("#" * 36)
        self._logger.info("\n".join(lines))
