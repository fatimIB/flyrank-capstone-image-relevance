"""
Tests for the mismatch guard's category-mismatch rejection (§12 Probe 3:
"force the wolf as a candidate for the fox post -> guard rejects it").

Run: pytest tests/test_guard.py -v
"""

from app.models.database import get_session
from app.models.db_models import Post, ImageMetadataRow, ImageEmbedding, PostEmbedding
from app.services.matching_engine import apply_guard
from app.services.similarity import cosine_similarity


def test_wolf_image_rejected_on_fox_post():
    """
    A correctly-labeled wolf image (category='wolf'), forced as a
    candidate for the fox post (expected_category='fox'), must be
    rejected by rule 3 (category mismatch) -- regardless of similarity
    score, since the categories genuinely disagree.
    """
    session = get_session()
    try:
        fox_post = session.query(Post).filter(Post.id == 1).first()
        assert fox_post is not None, "Fox post (id=1) not found — run seed_posts.py first"
        assert fox_post.expected_category == "fox"

        fox_post_embedding = (
            session.query(PostEmbedding)
            .filter(PostEmbedding.post_id == 1)
            .first()
        )
        assert fox_post_embedding is not None, "Fox post has no embedding — run generate_embeddings.py first"

        # image_id=13 is a correctly-labeled wolf image from the Phase 2 batch run
        wolf_metadata = (
            session.query(ImageMetadataRow)
            .filter(ImageMetadataRow.image_id == 13)
            .first()
        )
        assert wolf_metadata is not None, "image_id=13 metadata not found — run process_images.py first"
        assert wolf_metadata.category == "wolf", (
            f"Expected image 13 to be categorized 'wolf', got '{wolf_metadata.category}' "
            "-- test assumption no longer holds, pick a different known-wolf image_id"
        )

        wolf_embedding = (
            session.query(ImageEmbedding)
            .filter(ImageEmbedding.image_id == 13)
            .first()
        )
        assert wolf_embedding is not None, "image_id=13 has no embedding — run generate_embeddings.py first"

        similarity = cosine_similarity(fox_post_embedding.embedding, wolf_embedding.embedding)
        result = apply_guard(wolf_metadata, similarity, fox_post)

        assert result.status == "rejected", (
            f"Expected wolf image forced onto fox post to be REJECTED, "
            f"got '{result.status}' (reason: {result.reason})"
        )
        assert "category mismatch" in result.reason.lower(), (
            f"Expected rejection reason to mention category mismatch, got: {result.reason}"
        )
        assert "wolf" in result.reason.lower() and "fox" in result.reason.lower(), (
            f"Expected rejection reason to name both categories, got: {result.reason}"
        )

        print(f"\nForced wolf image (id=13) onto fox post:")
        print(f"  similarity: {similarity:.3f}")
        print(f"  status: {result.status}")
        print(f"  reason: {result.reason}")
    finally:
        session.close()