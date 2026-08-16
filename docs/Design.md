# Design Doc — AI Image Understanding & Content Matching Engine

## 1. Problem

Given a blog post, recommend the best-matching image from a small library —
or say honestly that no image is good enough. Wrong matches (e.g. a wolf
photo on a fox article) must be caught and rejected with a clear reason,
not silently returned.

**Non-goal:** this system does not generate images, does not build a
custom vision model, and does not compare multiple vision/embedding
models — one of each is enough (see brief §7).

## 2. Dataset

- 50 images, 5 categories: fox, wolf, dog, bear, deer (10 each)
- Sourced from Pexels (free license)
- Stored in `imgs/<category>/`, category folder name doubles as ground-truth
  label for the eval set later
- A handful of lower-quality/ambiguous shots included on purpose, so the
  vision model has something to flag as low-confidence (see §12, Probe 1)

## 3. Image metadata schema (vision model output)

Every image is sent to the vision model and must return JSON matching
this shape. Validated with Pydantic — invalid output is never trusted.

```python
class ImageMetadata(BaseModel):
    subject: str          # specific thing seen, e.g. "red fox"
    category: str         # controlled label: fox | wolf | dog | bear | deer
    attributes: list[str] # e.g. ["orange fur", "forest", "standing"]
    caption: str          # one sentence, used for embedding
    confidence: float     # 0.0–1.0, model's own certainty
```

**Why these fields:**
- `subject` vs `category` — subject is free-text (what the model actually
  saw), category is the controlled label compared against the image's
  source folder for the eval set.
- `attributes` — extra signal for the guard beyond subject/category alone.
- `caption` — this is what gets embedded (captions carry more semantic
  meaning than raw tags).
- `confidence` — drives the low-confidence flagging rule below.

**Validation rule:** if `confidence < 0.5`, the image is marked
`needs_review` instead of being trusted automatically.

## 4. Matching strategy

1. Embed each image's `caption`.
2. Embed each post's text.
3. For a given post, compute cosine similarity against every image embedding.
4. Rank candidates by similarity, highest first.
5. Pass the top candidate through the mismatch guard (§5) before returning it.

## 5. Mismatch guard — decision rules

Applied to the top-ranked candidate, in order:

```
1. confidence >= 0.5 ?
   NO  → REJECT: "low vision confidence, needs review"

2. similarity >= threshold (start: 0.75, tuned against eval set in Phase 4) ?
   NO  → REJECT: "no confident match, similarity below threshold"

3. image.category == post.expected_category ?
   NO  → REJECT: "category mismatch: expected {expected}, detected {actual}"
   YES → ACCEPT
```

Each post is manually tagged with an `expected_category` at creation time
(e.g. the fox test post is tagged `fox`) — this keeps rule 3 simple, instead of inferring topic from free text.

Rejections always return a `reason` string — never just `false`.

## 6. Database design

Six tables, kept intentionally small for a 50-image / 5-category scope.

```
images
  id, filename, folder_category, status

image_metadata
  image_id (FK), subject, category, attributes, caption, confidence

posts
  id, title, content, expected_category

image_embeddings
  image_id (FK), embedding

post_embeddings
  post_id (FK), embedding

suggestions
  id, post_id (FK), image_id (FK), similarity, status (accepted/rejected),
  reason, human_decision (pending/approved/rejected)
```

`approvals` was merged into `suggestions` as a `human_decision` column
rather than kept as a separate table.

## 7. Open questions / things to revisit in later phases

- Similarity threshold (0.75) is a starting guess — must be tuned against
  the labeled eval set in Phase 4, not left as-is.
- Whether `pgvector` is worth adding, or plain array columns + Python-side
  cosine similarity are enough at 50 images (leaning: plain arrays, simpler).
