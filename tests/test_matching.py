"""
Tests for matching accuracy — confirms the ranking logic itself (not
the guard, which is tested separately in test_guard.py) correctly
surfaces a same-category image as the top candidate for a clear-cut
post. Only top-1 is checked, matching the actual system design
(get_suggestion_for_post takes candidates[0] only — see
docs/Design.md §5).

Run: pytest tests/test_matching.py -v
"""

from app.models.database import get_session
from app.models.db_models import Post
from app.services.matching_engine import rank_candidates


def test_fox_post_ranks_fox_image_first():
    """
    §12 Probe 2: "the fox image ranks first; wolf and dog rank clearly
    lower." Checks the ranking logic directly, independent of the
    guard's accept/reject decision — this test would fail if
    rank_candidates ever had a sorting bug, even if the guard's own
    logic were untouched.
    """
    session = get_session()
    try:
        fox_post = session.query(Post).filter(Post.id == 1).first()
        assert fox_post is not None, "Fox post (id=1) not found — run seed_posts.py first"
        assert fox_post.expected_category == "fox"

        candidates = rank_candidates(session, fox_post)
        assert len(candidates) > 0, "No candidates returned — run generate_embeddings.py first"

        top_image, top_metadata, top_similarity = candidates[0]

        assert top_metadata.category == "fox", (
            f"Expected top-ranked candidate for fox post to be category 'fox', "
            f"got '{top_metadata.category}' (image_id={top_image.id})"
        )

        # Candidates should be sorted highest-similarity first
        scores = [score for _, _, score in candidates]
        assert scores == sorted(scores, reverse=True), (
            "Candidates are not sorted by similarity, descending"
        )

        print(f"\nFox post top candidate: image_id={top_image.id}, "
              f"category={top_metadata.category}, similarity={top_similarity:.3f}")
    finally:
        session.close()


def test_dog_post_ranks_dog_category_first():
    """
    Same check for the dog post. Note: the top-ranked image (image_id=19)
    is genuinely category='dog' per the vision model's own (incorrect)
    classification — this test checks the RANKING is internally
    consistent with stored metadata, not whether that metadata is
    itself correct (that's what run_eval.py measures separately,
    against ground truth).
    """
    session = get_session()
    try:
        dog_post = session.query(Post).filter(Post.id == 3).first()
        assert dog_post is not None, "Dog post (id=3) not found — run seed_posts.py first"
        assert dog_post.expected_category == "dog"

        candidates = rank_candidates(session, dog_post)
        assert len(candidates) > 0, "No candidates returned — run generate_embeddings.py first"

        top_image, top_metadata, top_similarity = candidates[0]

        assert top_metadata.category == "dog", (
            f"Expected top-ranked candidate for dog post to be category 'dog' "
            f"(per stored metadata), got '{top_metadata.category}'"
        )

        print(f"\nDog post top candidate: image_id={top_image.id}, "
              f"category={top_metadata.category}, similarity={top_similarity:.3f}")
    finally:
        session.close()


def test_unrelated_post_scores_far_below_topical_posts():
    """
    §12 Probe 4 support: the Roman aqueducts post's best candidate
    should score far lower than any topical post's best candidate,
    confirming the embedding model genuinely distinguishes unrelated
    content rather than just returning arbitrary scores.
    """
    session = get_session()
    try:
        fox_post = session.query(Post).filter(Post.id == 1).first()
        aqueducts_post = session.query(Post).filter(Post.id == 6).first()
        assert fox_post is not None and aqueducts_post is not None

        fox_candidates = rank_candidates(session, fox_post)
        aqueducts_candidates = rank_candidates(session, aqueducts_post)

        fox_top_score = fox_candidates[0][2]
        aqueducts_top_score = aqueducts_candidates[0][2]

        assert aqueducts_top_score < fox_top_score, (
            "Expected the unrelated post's best score to be lower than "
            "the fox post's best score"
        )
        # Not just lower -- meaningfully lower, not a close call
        assert aqueducts_top_score < 0.2, (
            f"Expected unrelated post's top score to be clearly low, "
            f"got {aqueducts_top_score:.3f}"
        )

        print(f"\nFox post top score: {fox_top_score:.3f}, "
              f"Aqueducts post top score: {aqueducts_top_score:.3f}")
    finally:
        session.close()