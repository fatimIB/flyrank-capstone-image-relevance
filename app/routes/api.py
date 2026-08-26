"""
API routes — the matching engine endpoint (which creates suggestions)
and the human review workflow (inspecting, approving, rejecting them).
Kept in one file since the whole API surface is small (4 endpoints).
"""

from fastapi import APIRouter, HTTPException

from app.models.database import get_session
from app.models.db_models import Suggestion, Post, Image
from app.services.matching_engine import get_suggestion_for_post

router = APIRouter()


@router.get("/posts/{post_id}/images")
def get_image_suggestion(post_id: int):
    """
    Runs the matching engine for a post, saves the result as a new
    Suggestion row, and returns it. This is the main "find me an image"
    endpoint — every call creates a fresh suggestion record.
    """
    try:
        suggestion = get_suggestion_for_post(post_id, persist=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "suggestion_id": suggestion.id,
        "post_id": suggestion.post_id,
        "image_id": suggestion.image_id,
        "similarity": suggestion.similarity,
        "status": suggestion.status,
        "reason": suggestion.reason,
        "human_decision": suggestion.human_decision,
    }


@router.get("/suggestions/{suggestion_id}")
def get_suggestion(suggestion_id: int):
    """Inspect a specific suggestion — the post, image, and why the guard decided what it did."""
    session = get_session()
    try:
        suggestion = session.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
        if suggestion is None:
            raise HTTPException(status_code=404, detail=f"No suggestion with id={suggestion_id}")

        post = session.query(Post).filter(Post.id == suggestion.post_id).first()
        image = (
            session.query(Image).filter(Image.id == suggestion.image_id).first()
            if suggestion.image_id is not None
            else None
        )

        return {
            "suggestion_id": suggestion.id,
            "post": {"id": post.id, "title": post.title, "expected_category": post.expected_category} if post else None,
            "image": {"id": image.id, "filename": image.filename, "category": image.folder_category} if image else None,
            "similarity": suggestion.similarity,
            "status": suggestion.status,
            "reason": suggestion.reason,
            "human_decision": suggestion.human_decision,
        }
    finally:
        session.close()


@router.post("/suggestions/{suggestion_id}/approve")
def approve_suggestion(suggestion_id: int):
    """Human review: mark a suggestion as approved."""
    return _set_human_decision(suggestion_id, "approved")


@router.post("/suggestions/{suggestion_id}/reject")
def reject_suggestion(suggestion_id: int):
    """Human review: mark a suggestion as rejected, overriding the guard if needed."""
    return _set_human_decision(suggestion_id, "rejected")


def _set_human_decision(suggestion_id: int, decision: str):
    session = get_session()
    try:
        suggestion = session.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
        if suggestion is None:
            raise HTTPException(status_code=404, detail=f"No suggestion with id={suggestion_id}")

        suggestion.human_decision = decision
        session.commit()

        return {
            "suggestion_id": suggestion.id,
            "human_decision": suggestion.human_decision,
            "message": f"Suggestion {suggestion_id} marked as {decision} by human review.",
        }
    finally:
        session.close()