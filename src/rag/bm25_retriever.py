from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from .text_utils import tokenize


class BM25Retriever:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs: list[dict[str, Any]] = []
        self.doc_tokens: list[list[str]] = []
        self.doc_lens: list[int] = []
        self.df: Counter[str] = Counter()
        self.avgdl = 0.0

    def add(self, doc: dict[str, Any]) -> None:
        tokens = tokenize(doc.get("text", ""))
        self.docs.append(doc)
        self.doc_tokens.append(tokens)
        self.doc_lens.append(len(tokens))
        self.df.update(set(tokens))
        self.avgdl = float(sum(self.doc_lens)) / max(len(self.doc_lens), 1)

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if not self.docs:
            return []

        q_terms = tokenize(query)
        if not q_terms:
            return []

        n_docs = len(self.docs)
        scores = np.zeros(n_docs, dtype=np.float32)
        for term in q_terms:
            df = self.df.get(term, 0)
            if df == 0:
                continue
            idf = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            for i, tokens in enumerate(self.doc_tokens):
                tf = tokens.count(term)
                if tf == 0:
                    continue
                denom = tf + self.k1 * (1.0 - self.b + self.b * self.doc_lens[i] / max(self.avgdl, 1e-6))
                scores[i] += idf * (tf * (self.k1 + 1.0)) / max(denom, 1e-6)

        idx = np.argsort(-scores)[:top_k]
        out: list[dict[str, Any]] = []
        for i in idx:
            score = float(scores[i])
            if score <= 0:
                continue
            out.append({**self.docs[i], "bm25_score": score})
        return out
