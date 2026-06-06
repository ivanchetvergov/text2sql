from __future__ import annotations

from typing import Any

from .bm25_retriever import BM25Retriever
from .constants import CANDIDATES_PER_SLOT
from .cross_encoder_scorer import MiniCrossEncoderScorer
from .faiss_retriever import FaissRetriever
from .text_utils import doc_key


class HybridRetriever:
    def __init__(self, dense: dict[str, FaissRetriever], bm25: dict[str, BM25Retriever], scorer: MiniCrossEncoderScorer) -> None:
        self._dense = dense
        self._bm25 = bm25
        self._scorer = scorer

    def add(self, slot: str, doc: dict[str, Any]) -> None:
        self._dense[slot].add(doc)
        self._bm25[slot].add(doc)

    def search(self, slot: str, query: str, top_k: int) -> list[dict[str, Any]]:
        candidate_k = max(top_k, CANDIDATES_PER_SLOT.get(slot, top_k))
        bm25_items = self._bm25[slot].search(query, top_k=candidate_k)
        dense_items = self._dense[slot].search(query, top_k=candidate_k)

        merged: dict[str, dict[str, Any]] = {}
        for item in bm25_items:
            merged[doc_key(item)] = dict(item)
        for item in dense_items:
            key = doc_key(item)
            if key in merged:
                merged[key].setdefault("dense_score", float(item.get("dense_score", 0.0)))
            else:
                merged[key] = dict(item)

        candidates = list(merged.values())
        rerank_scores = self._scorer.score(query, candidates)
        for item, score in zip(candidates, rerank_scores):
            item["_score"] = float(score)

        return sorted(candidates, key=lambda x: float(x.get("_score", 0.0)), reverse=True)[:top_k]
