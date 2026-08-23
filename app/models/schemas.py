"""
Pydantic schemas — these validate data coming IN from untrusted sources
(the vision model's raw response). Nothing from the AI gets stored or
used until it passes these checks.
"""

from pydantic import BaseModel, Field, field_validator


ALLOWED_CATEGORIES = {"fox", "wolf", "dog", "bear", "deer"}


class ImageMetadata(BaseModel):
    """
    Structure we expect back from the vision model for a single image.
    If Gemini's response doesn't match this shape, Pydantic raises a
    validation error and we treat the call as failed (see vision_service.py).
    """
    subject: str = Field(..., min_length=1)
    category: str
    attributes: list[str] = Field(default_factory=list)
    caption: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("category")
    @classmethod
    def category_must_be_known(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(
                f"category '{v}' not in allowed set {ALLOWED_CATEGORIES}"
            )
        return v

    @property
    def needs_review(self) -> bool:
        """Low-confidence results get flagged, never silently trusted."""
        return self.confidence < 0.5