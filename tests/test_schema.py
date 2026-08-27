"""
Tests for ImageMetadata schema validation — confirms the vision
pipeline's core safety rule: invalid model output is never accepted.

Run: pytest tests/test_schema.py -v
"""

import pytest
from pydantic import ValidationError

from app.models.schemas import ImageMetadata


def test_valid_data_is_accepted():
    """A well-formed response should pass validation without error."""
    data = {
        "subject": "red fox",
        "category": "fox",
        "attributes": ["orange fur", "forest"],
        "caption": "A red fox standing in a forest",
        "confidence": 0.95,
    }
    metadata = ImageMetadata(**data)
    assert metadata.subject == "red fox"
    assert metadata.category == "fox"
    assert metadata.confidence == 0.95


def test_missing_required_field_is_rejected():
    """Missing a required field (confidence) must raise, not silently pass."""
    data = {
        "subject": "red fox",
        "category": "fox",
        "attributes": ["orange fur"],
        "caption": "A red fox in a forest",
        # confidence missing
    }
    with pytest.raises(ValidationError):
        ImageMetadata(**data)


def test_confidence_out_of_range_is_rejected():
    """Confidence must be within 0.0-1.0 — a value like 1.5 is invalid."""
    data = {
        "subject": "red fox",
        "category": "fox",
        "attributes": [],
        "caption": "A red fox in a forest",
        "confidence": 1.5,
    }
    with pytest.raises(ValidationError):
        ImageMetadata(**data)


def test_negative_confidence_is_rejected():
    """Confidence below 0.0 is also invalid."""
    data = {
        "subject": "red fox",
        "category": "fox",
        "attributes": [],
        "caption": "A red fox in a forest",
        "confidence": -0.1,
    }
    with pytest.raises(ValidationError):
        ImageMetadata(**data)


def test_unknown_category_is_rejected():
    """
    category must be one of the 5 known values. A model hallucinating
    an out-of-scope category (e.g. "elephant") must be caught, not
    silently stored.
    """
    data = {
        "subject": "elephant",
        "category": "elephant",
        "attributes": [],
        "caption": "An elephant in a field",
        "confidence": 0.9,
    }
    with pytest.raises(ValidationError):
        ImageMetadata(**data)


def test_empty_subject_is_rejected():
    """subject must not be an empty string."""
    data = {
        "subject": "",
        "category": "fox",
        "attributes": [],
        "caption": "A red fox in a forest",
        "confidence": 0.9,
    }
    with pytest.raises(ValidationError):
        ImageMetadata(**data)


def test_category_is_case_normalized():
    """
    The vision model might return inconsistent casing (e.g. "Fox"
    instead of "fox"). The schema should normalize this rather than
    reject valid data over a casing difference.
    """
    data = {
        "subject": "red fox",
        "category": "FOX",
        "attributes": [],
        "caption": "A red fox in a forest",
        "confidence": 0.9,
    }
    metadata = ImageMetadata(**data)
    assert metadata.category == "fox"


def test_needs_review_flag_below_threshold():
    """confidence below 0.5 must set needs_review to True."""
    data = {
        "subject": "red fox",
        "category": "fox",
        "attributes": [],
        "caption": "A blurry, uncertain photo",
        "confidence": 0.3,
    }
    metadata = ImageMetadata(**data)
    assert metadata.needs_review is True


def test_needs_review_flag_above_threshold():
    """confidence at or above 0.5 must set needs_review to False."""
    data = {
        "subject": "red fox",
        "category": "fox",
        "attributes": [],
        "caption": "A clear photo of a fox",
        "confidence": 0.5,
    }
    metadata = ImageMetadata(**data)
    assert metadata.needs_review is False