"""
Embedding service — turns text (image captions, post content) into
vectors using a local sentence-transformers model. No API key, no
rate limits, same library used in AskFatima.
"""

from sentence_transformers import SentenceTransformer

# Loaded once, reused for every call — loading the model is the slow
# part, so we don't want to reload it per-text.
_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    """
    Turns a piece of text into a vector (list of floats). Same model
    used for both image captions and post content, so they land in the
    same vector space and can be meaningfully compared.
    """
    model = get_model()
    vector = model.encode(text)
    return vector.tolist()  # numpy array -> plain list, so it's JSON-storable