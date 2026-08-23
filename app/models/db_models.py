"""
SQLAlchemy models — these define what actually gets STORED in the
database. Separate from schemas.py (which validates incoming AI output).
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, DateTime, JSON, Text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    folder_category = Column(String, nullable=False)  # ground truth from folder name
    status = Column(String, default="pending")  # pending | processed | failed
    created_at = Column(DateTime, default=utcnow)

    metadata_row = relationship("ImageMetadataRow", back_populates="image", uselist=False)
    embedding_row = relationship("ImageEmbedding", back_populates="image", uselist=False)


class ImageMetadataRow(Base):
    __tablename__ = "image_metadata"

    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=False, unique=True)
    subject = Column(String, nullable=False)
    category = Column(String, nullable=False)
    attributes = Column(JSON, default=list)
    caption = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    needs_review = Column(Integer, default=0)  # 0/1 boolean flag

    image = relationship("Image", back_populates="metadata_row")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    expected_category = Column(String, nullable=False)

    embedding_row = relationship("PostEmbedding", back_populates="post", uselist=False)


class ImageEmbedding(Base):
    __tablename__ = "image_embeddings"

    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=False, unique=True)
    embedding = Column(JSON, nullable=False)  # stored as a plain list of floats

    image = relationship("Image", back_populates="embedding_row")


class PostEmbedding(Base):
    __tablename__ = "post_embeddings"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, unique=True)
    embedding = Column(JSON, nullable=False)

    post = relationship("Post", back_populates="embedding_row")


class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=False)
    similarity = Column(Float, nullable=False)
    status = Column(String, nullable=False)  # accepted | rejected
    reason = Column(String, nullable=False)
    human_decision = Column(String, default="pending")  # pending | approved | rejected
    created_at = Column(DateTime, default=utcnow)


class AIUsageLog(Base):
    """Cost tracking — one row per AI call (vision or embedding)."""
    __tablename__ = "ai_usage_log"

    id = Column(Integer, primary_key=True)
    operation = Column(String, nullable=False)  # "vision" | "embedding"
    model = Column(String, nullable=False)
    reference_id = Column(Integer, nullable=True)  # image_id or post_id
    status = Column(String, nullable=False)  # success | failed
    estimated_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)