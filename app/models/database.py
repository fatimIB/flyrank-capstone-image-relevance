"""
Database connection setup. Using SQLite for simplicity at this scale
(15 images, a handful of posts) — swapping to PostgreSQL later only
means changing DATABASE_URL, nothing else in the code changes.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./capstone.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()