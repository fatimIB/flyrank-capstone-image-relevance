"""
Vision service — sends an image to a local Ollama vision model (llava),
validates the response against our schema, retries on transient failure,
and never trusts invalid output.

Core rule from the brief: the model is an untrusted external source.
Nothing gets stored until it passes ImageMetadata validation.

Uses Ollama running locally — no API key, no rate limits, fully offline.
Requires: `ollama pull llava` done once beforehand, and the Ollama
background service running (it starts automatically after install on
most systems).
"""

import os
import json
import time
import ollama
from pydantic import ValidationError

from app.models.schemas import ImageMetadata

# Model name comes from .env so you can swap models without touching code
# — set OLLAMA_MODEL in your .env file (defaults to "llava" if unset).
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llava")

VISION_PROMPT = """
Look at this image and respond with ONLY valid JSON, no other text,
no markdown formatting, matching exactly this shape:

{
  "subject": "<specific thing you see, e.g. 'red fox'>",
  "category": "<one of: fox, wolf, dog, bear, deer>",
  "attributes": ["<short attribute>", "<short attribute>", "..."],
  "caption": "<one sentence describing the image>",
  "confidence": <float between 0.0 and 1.0, how sure you are>
}
"""

MAX_RETRIES = 3


def _call_ollama_vision(image_path: str) -> str:
    """
    Single raw call to the local vision model. May raise if Ollama isn't
    running, the model isn't pulled, or the image can't be read.
    """
    response = ollama.generate(
        model=MODEL_NAME,
        prompt=VISION_PROMPT,
        images=[image_path],
    )
    return response["response"]


def _parse_and_validate(raw_text: str) -> ImageMetadata:
    """
    Strip any accidental markdown fences, parse JSON, validate against
    the schema. Raises ValueError/ValidationError if the output is bad —
    caller decides whether to retry.

    Local vision models are more prone to wrapping JSON in explanatory
    text than Gemini was, so we also try to extract just the {...} block
    as a fallback before giving up.
    """
    cleaned = raw_text.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # fallback: grab the first {...} block in case the model added
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise
        data = json.loads(cleaned[start:end + 1])

    return ImageMetadata(**data)  # can raise pydantic.ValidationError


def classify_image(image_path: str) -> tuple[ImageMetadata | None, dict]:
    """
    Attempts to classify one image, retrying on failure up to MAX_RETRIES
    times. Returns (metadata_or_None, cost_log_entry).

    metadata is None only if every retry failed — caller marks the image
    as 'failed' rather than guessing.
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = _call_ollama_vision(image_path)
            metadata = _parse_and_validate(raw)

            return metadata, {
                "operation": "vision",
                "model": MODEL_NAME,
                "status": "success",
                # Local model — no per-call cost, but we still log every
                # call so cost-tracking is a real, working habit (and
                # this column just stays $0 for a local model).
                "estimated_cost": 0.0,
            }

        except (json.JSONDecodeError, ValidationError) as e:
            # The model gave us garbage or invalid data — worth retrying,
            # a fresh call might succeed (local models can be inconsistent
            # about following the JSON-only instruction).
            last_error = f"invalid output: {e}"
        except Exception as e:
            # Ollama not running, model not pulled, file read error, etc.
            last_error = f"call failed: {e}"

        if attempt < MAX_RETRIES:
            time.sleep(1.0 * attempt)  # small backoff between retries

    # every retry failed
    return None, {
        "operation": "vision",
        "model": MODEL_NAME,
        "status": "failed",
        "estimated_cost": 0.0,
        "error": last_error,
    }