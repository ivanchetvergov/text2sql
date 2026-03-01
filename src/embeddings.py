from sentence_transformers import SentenceTransformer
import torch

_E5_MODELS = {
    "intfloat/multilingual-e5-large",
    "intfloat/multilingual-e5-base",
}


class EmbeddingModel:

    def __init__(self, model_name: str = "intfloat/multilingual-e5-large"):
        self.model = SentenceTransformer(model_name)
        self._use_prefix = model_name in _E5_MODELS

        if torch.backends.mps.is_available():
            self.model = self.model.to("mps")

    @property
    def dim(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def embed(self, text: str, is_query: bool = False) -> list[float]:
        if self._use_prefix:
            text = ("query: " if is_query else "passage: ") + text
        emb = self.model.encode(text, convert_to_numpy=True)
        return emb.tolist()

