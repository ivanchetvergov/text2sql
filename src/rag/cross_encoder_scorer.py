from __future__ import annotations

from typing import Any

import numpy as np

from .text_utils import tokenize


class MiniCrossEncoderScorer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._model = None
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as exc:
            self._logger.warning("Cross-encoder init failed, using lexical fallback: %s", exc)

    def score(self, query: str, docs: list[dict[str, Any]]) -> list[float]:
        if not docs:
            return []

        if self._model is None:
            q_terms = set(tokenize(query))
            scores: list[float] = []
            for doc in docs:
                d_terms = set(tokenize(doc.get("text", "")))
                overlap = len(q_terms & d_terms) / max(len(q_terms), 1)
                scores.append(float(overlap))
            return scores

        pairs = [(query, doc.get("text", "")) for doc in docs]
        raw = self._model.predict(pairs)
        if isinstance(raw, np.ndarray):
            return raw.astype(np.float32).tolist()
        return [float(x) for x in raw]
