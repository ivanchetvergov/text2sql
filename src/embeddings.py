from typing import List, Optional
from sentence_transformers import SentenceTransformer
import torch

class EmbeddingModel:

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

        if torch.backends.mps.is_available():
            self.model = self.model.to("mps")

    @property
    def dim(self) -> int:
        """Embedding dimensionality returned by the model."""
        return self.model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        emb = self.model.encode(text, convert_to_numpy=True)
        return emb.tolist()

