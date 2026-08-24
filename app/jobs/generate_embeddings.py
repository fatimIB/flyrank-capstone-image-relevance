"""
Batch job — generates embeddings for every processed image's caption
and every post's content, storing them for later similarity comparison.
Idempotent: skips anything already embedded, safe to re-run.

Run: python -m app.jobs.generate_embeddings
"""

from app.models.database import get_session, init_db
from app.models.db_models import (
    Image, ImageMetadataRow, ImageEmbedding, Post, PostEmbedding, AIUsageLog
)
from app.services.embedding_service import embed_text

MODEL_NAME = "all-MiniLM-L6-v2"


def embed_images(session):
    """Embed every processed image's caption that doesn't have an embedding yet."""
    already_embedded_ids = {row.image_id for row in session.query(ImageEmbedding).all()}

    metadata_rows = (
        session.query(ImageMetadataRow)
        .filter(~ImageMetadataRow.image_id.in_(already_embedded_ids))
        .all()
    )

    print(f"Embedding {len(metadata_rows)} image captions...")
    for row in metadata_rows:
        vector = embed_text(row.caption)

        session.add(ImageEmbedding(image_id=row.image_id, embedding=vector))
        session.add(AIUsageLog(
            operation="embedding",
            model=MODEL_NAME,
            reference_id=row.image_id,
            status="success",
            estimated_cost=0.0,  # local model, no per-call cost
        ))
        print(f"  image_id={row.image_id} -> embedded ({row.category})")

    session.commit()


def embed_posts(session):
    """Embed every post's content that doesn't have an embedding yet."""
    already_embedded_ids = {row.post_id for row in session.query(PostEmbedding).all()}

    posts = (
        session.query(Post)
        .filter(~Post.id.in_(already_embedded_ids))
        .all()
    )

    print(f"Embedding {len(posts)} posts...")
    for post in posts:
        vector = embed_text(post.content)

        session.add(PostEmbedding(post_id=post.id, embedding=vector))
        session.add(AIUsageLog(
            operation="embedding",
            model=MODEL_NAME,
            reference_id=post.id,
            status="success",
            estimated_cost=0.0,
        ))
        print(f"  post_id={post.id} -> embedded ({post.title})")

    session.commit()


def run():
    init_db()
    session = get_session()
    try:
        embed_images(session)
        embed_posts(session)
        print("\nDone.")
    finally:
        session.close()


if __name__ == "__main__":
    run()