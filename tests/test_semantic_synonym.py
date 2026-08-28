"""
Standalone semantic-matching test — never inserted into the database
or seed_posts.py. Tests the matching engine with a post about
Vulpes vulpes (the scientific name for red fox) that never uses the
word "fox", to demonstrate matching works on meaning, not keywords
(brief §4's own example).

The Post object here is a plain in-memory SQLAlchemy model instance —
it is never added to a session or committed, so nothing is persisted.

Run: pytest tests/test_semantic_synonym.py -v -s
"""

from app.models.database import get_session
from app.models.db_models import Post, Image, ImageMetadataRow, ImageEmbedding
from app.services.matching_engine import apply_guard
from app.services.similarity import cosine_similarity
from app.services.embedding_service import embed_text


def test_scientific_name_semantically_matches_fox_image():
    """
    A post about Vulpes vulpes, using only fox-specific physical and
    behavioral traits (never habitat words that could overlap with
    other animals in the dataset, and never the word "fox" itself),
    should still surface a fox image as the top semantic match.
    """
    post = Post(
        title="Vulpes vulpes: A Wild Canid Species",
        content=(
            "Vulpes vulpes is a wild canid distinguished by its bright "
            "orange-red fur, narrow pointed snout, triangular upright "
            "ears, and long bushy tail with a white tip. This solitary "
            "predator hunts small rodents and birds using keen "
            "hearing and quick, agile movements. Unlike larger canids, "
            "it has slender legs and a lightweight frame built for "
            "stealth rather than pack hunting."
        ),
        expected_category="fox",
    )

    # Confirm no keyword overlap — this is testing semantic matching,
    # not exact-word matching.
    assert "fox" not in post.title.lower()
    assert "fox" not in post.content.lower()

    # Embed this post in memory only — no DB write.
    post_vector = embed_text(f"{post.title}\n{post.content}")

    session = get_session()
    try:
        candidates = []
        for emb_row in session.query(ImageEmbedding).all():
            image = session.query(Image).filter(Image.id == emb_row.image_id).first()
            metadata = (
                session.query(ImageMetadataRow)
                .filter(ImageMetadataRow.image_id == emb_row.image_id)
                .first()
            )
            if image is None or metadata is None:
                continue

            score = cosine_similarity(post_vector, emb_row.embedding)
            candidates.append((image, metadata, score))

        candidates.sort(key=lambda c: c[2], reverse=True)
        assert candidates, "No image candidates found — run generate_embeddings.py first"

        top_image, top_metadata, top_similarity = candidates[0]

        print("\nSemantic synonym test")
        print("---------------------")
        print("Post: Vulpes vulpes: A Wild Canid Species (never says 'fox')")
        print(f"Top image ID: {top_image.id}")
        print(f"Detected category: {top_metadata.category}")
        print(f"Similarity: {top_similarity:.3f}")

        result = apply_guard(top_metadata, top_similarity, post)
        print(f"Guard status: {result.status}")
        print(f"Guard reason: {result.reason}")

        assert top_metadata.category == "fox", (
            f"Expected semantic search to surface a fox image first, "
            f"got category='{top_metadata.category}' (image_id={top_image.id})"
        )
        assert result.status == "accepted", (
            f"Expected acceptance, got status='{result.status}' (reason: {result.reason})"
        )
    finally:
        session.close()