from __future__ import annotations

from typing import Any

import faiss
import numpy as np

from .embeddings import EmbeddingModel


class FaissRetriever:
    def __init__(self, embed_model: EmbeddingModel) -> None:
        self.embed = embed_model
        self.dim = int(self.embed.dim)
        self.idx = faiss.IndexFlatIP(self.dim)
        self.docs: list[dict[str, Any]] = []

    def _embed(self, text: str, is_query: bool = False) -> np.ndarray:
        vec = np.array(self.embed.embed(text, is_query=is_query), dtype="float32").reshape(1, -1)
        faiss.normalize_L2(vec)
        return vec

    def add(self, doc: dict[str, Any]) -> None:
        self.idx.add(self._embed(doc.get("text", ""), is_query=False))
        self.docs.append(doc)

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if self.idx.ntotal == 0:
            return []

        qv = self._embed(query, is_query=True)
        dists, ids = self.idx.search(qv, min(top_k, self.idx.ntotal))

        out: list[dict[str, Any]] = []
        for score, i in zip(dists[0], ids[0]):
            if i == -1:
                continue
            out.append({**self.docs[i], "dense_score": float(score)})
        return out
