"""
Similarity utilities — plain Python cosine similarity. At 50 images,
no need for a vector database (pgvector, etc.) — comparing against
every image directly is fast enough and much simpler to explain.
"""

import math


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Returns a score between -1 and 1 (in practice, usually 0-1 for text
    embeddings) representing how close two vectors are in meaning.
    1.0 = identical direction, 0 = unrelated, negative = opposite.
    """
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)