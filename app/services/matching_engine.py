"""
Matching engine + mismatch guard — the core of the whole capstone.

Given a post, ranks all images by similarity, then runs the guard on
the top candidate to decide: accept, reject (with reason), or "no
confident match."

Guard rules (see docs/Design.md §6), applied in order to the top
candidate:
  1. confidence >= 0.5           -> else reject: low confidence
  2. similarity >= threshold     -> else reject: no confident match
  3. image.category == post.expected_category -> else reject: mismatch
"""

from dataclasses import dataclass

from app.models.database import get_session
from app.models.db_models import (
    Image, ImageMetadataRow, ImageEmbedding, Post, PostEmbedding, Suggestion
)
from app.services.similarity import cosine_similarity

SIMILARITY_THRESHOLD = 0.4  # updated from 0.75 after real testing — see
                             # Design.md §8 / BUILDLOG.md for reasoning
CONFIDENCE_THRESHOLD = 0.5


@dataclass
class GuardResult:
    status: str          # "accepted" | "rejected"
    reason: str
    image_id: int | None
    similarity: float | None


def rank_candidates(session, post: Post) -> list[tuple[Image, ImageMetadataRow, float]]:
    """
    Returns every processed image ranked by similarity to the post,
    highest first. Each entry is (Image, ImageMetadataRow, similarity).
    """
    post_embedding_row = (
        session.query(PostEmbedding).filter(PostEmbedding.post_id == post.id).first()
    )
    if post_embedding_row is None:
        raise ValueError(f"Post {post.id} has no embedding yet — run generate_embeddings first.")

    post_vector = post_embedding_row.embedding

    candidates = []
    image_embeddings = session.query(ImageEmbedding).all()

    for emb_row in image_embeddings:
        image = session.query(Image).filter(Image.id == emb_row.image_id).first()
        metadata = (
            session.query(ImageMetadataRow)
            .filter(ImageMetadataRow.image_id == emb_row.image_id)
            .first()
        )
        if image is None or metadata is None:
            continue  # skip anything incomplete

        score = cosine_similarity(post_vector, emb_row.embedding)
        candidates.append((image, metadata, score))

    candidates.sort(key=lambda c: c[2], reverse=True)
    return candidates


def apply_guard(metadata: ImageMetadataRow, similarity: float, post: Post) -> GuardResult:
    """
    Applies the three guard rules, in order, to a single candidate.
    Returns a GuardResult explaining the decision either way.
    """
    # Rule 1 — confidence
    if metadata.confidence < CONFIDENCE_THRESHOLD:
        return GuardResult(
            status="rejected",
            reason=f"low vision confidence ({metadata.confidence:.2f}), needs review",
            image_id=metadata.image_id,
            similarity=similarity,
        )

    # Rule 2 — similarity threshold
    if similarity < SIMILARITY_THRESHOLD:
        return GuardResult(
            status="rejected",
            reason=f"no confident match, similarity ({similarity:.2f}) below threshold ({SIMILARITY_THRESHOLD})",
            image_id=metadata.image_id,
            similarity=similarity,
        )

    # Rule 3 — category match
    if metadata.category != post.expected_category:
        return GuardResult(
            status="rejected",
            reason=f"category mismatch: expected '{post.expected_category}', detected '{metadata.category}'",
            image_id=metadata.image_id,
            similarity=similarity,
        )

    # All checks passed
    return GuardResult(
        status="accepted",
        reason="subject and category match, similarity above threshold",
        image_id=metadata.image_id,
        similarity=similarity,
    )


def get_suggestion_for_post(post_id: int, persist: bool = True) -> Suggestion | GuardResult:
    """
    Main entry point: given a post ID, ranks all images, takes the top
    candidate, and runs it through the guard. Only the top candidate is
    checked — if it fails, the result is "no confident match" rather
    than trying candidate #2, #3, etc. (kept simple per project scope).
 
    persist=True (default): saves the result as a real Suggestion row
    (human_decision starts as "pending") and returns that row. This is
    what the API routes use, since the review workflow needs something
    durable to approve/reject against.
 
    persist=False: returns the in-memory GuardResult only, nothing is
    written to the database. Useful for quick command-line checks or
    the eval script, where creating a permanent suggestion row isn't
    needed or wanted.
    """
    session = get_session()
    try:
        post = session.query(Post).filter(Post.id == post_id).first()
        if post is None:
            raise ValueError(f"No post with id={post_id}")
 
        candidates = rank_candidates(session, post)
        if not candidates:
            result = GuardResult(
                status="rejected",
                reason="no images available to compare against",
                image_id=None,
                similarity=None,
            )
        else:
            top_image, top_metadata, top_similarity = candidates[0]
            result = apply_guard(top_metadata, top_similarity, post)
 
        if not persist:
            return result
 
        suggestion = Suggestion(
            post_id=post_id,
            image_id=result.image_id,
            similarity=result.similarity if result.similarity is not None else 0.0,
            status=result.status,
            reason=result.reason,
            human_decision="pending",
        )
        session.add(suggestion)
        session.commit()
        session.refresh(suggestion)
        return suggestion
    finally:
        session.close()
 
 
if __name__ == "__main__":
    """
    Runs the matching engine against every post currently in the DB,
    saves each result as a real Suggestion row (same as the API does
    per-post), and prints a summary. Safe to re-run — each run creates
    fresh suggestion rows (old ones aren't deleted), so if you want a
    clean slate, clear the suggestions table first.
 
    Run: python -m app.services.matching_engine
    """
    session = get_session()
    try:
        posts = session.query(Post).all()
    finally:
        session.close()
 
    if not posts:
        print("No posts found — run `python -m app.jobs.seed_posts` first.")
    else:
        print(f"Creating suggestions for {len(posts)} posts:\n")
        for post in posts:
            suggestion = get_suggestion_for_post(post.id, persist=True)
            sim_str = f"{suggestion.similarity:.3f}" if suggestion.similarity is not None else "N/A"
            print(
                f"Post {post.id} ({post.title}) [expected: {post.expected_category}]\n"
                f"  -> saved as suggestion_id={suggestion.id} | {suggestion.status.upper()} | "
                f"image_id={suggestion.image_id} | similarity={sim_str}\n"
                f"  -> reason: {suggestion.reason}\n"
            )