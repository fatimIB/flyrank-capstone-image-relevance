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

## 3. Vision model

Using **Ollama + llava**, running locally. Originally planned to use
Gemini Flash (per the brief's suggested stack), but switched after two
real blockers: the initially-targeted model (gemini-2.0-flash) had been
deprecated and shut down, and the actual free-tier quota on its
replacement (gemini-3.5-flash) was only 20 requests/day — not enough to
reliably batch-process 50 images. Llava runs fully local, no API key, no
rate limits. See BUILDLOG.md for the full story.

## 4. Image metadata schema (vision model output)

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
`needs_review` instead of being trusted automatically. (Tested raising
this to 0.75 against real batch data — see §7, kept at 0.5.)

## 5. Matching strategy

1. Embed each image's `caption`.
2. Embed each post's text.
3. For a given post, compute cosine similarity against every image embedding.
4. Rank candidates by similarity, highest first.
5. Pass the top candidate through the mismatch guard (§6) before returning it.

## 6. Mismatch guard — decision rules

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
(e.g. the fox test post is tagged `fox`) — this keeps rule 3 simple,
instead of inferring topic from free text.

Rejections always return a `reason` string — never just `false`.

**Why rule 3 matters, with real evidence:** in the Phase 2 batch run,
llava misclassified 4/10 wolf photos as fox or dog — including one case
with confidence 1.00, wrongly labeled "dog." Confidence alone would not
have caught this (see §7). Rule 3's independent category check is what
catches it: a wolf photo mislabeled "dog" with high confidence still
fails the category-match check against a wolf-tagged post, and gets
correctly rejected.

## 7. Database design

Seven tables, kept intentionally small for a 50-image / 5-category scope.

```
images
  id, filename, folder_category, status

image_metadata
  image_id (FK), subject, category, attributes, caption, confidence, needs_review

posts
  id, title, content, expected_category

image_embeddings
  image_id (FK), embedding

post_embeddings
  post_id (FK), embedding

suggestions
  id, post_id (FK), image_id (FK), similarity, status (accepted/rejected),
  reason, human_decision (pending/approved/rejected)

ai_usage_log
  id, operation, model, reference_id, status, estimated_cost, created_at
```

`approvals` was merged into `suggestions` as a `human_decision` column
rather than kept as a separate table.

`ai_usage_log` covers the cost-tracking requirement — one row per AI
call (vision or embedding), success or failure, attributed with a cost
value (currently $0 across the board, since llava runs locally).

**Indexes:** foreign key columns (`image_id`, `post_id` on the embedding
and suggestion tables) are indexed to keep lookups fast when ranking
candidates for a post. `images.status` is indexed since the batch job
filters on it every run (`WHERE status = 'pending'`).

## 8. Open questions / resolved findings

- **Resolved — confidence threshold for `needs_review`:** tested raising
  it from 0.5 to 0.75 against the real batch output. The two rows that
  would newly get flagged were both CORRECT answers (0.7-confidence
  puppy photos), while every actual wolf misclassification sat at
  0.8–1.00 confidence and would still pass through unflagged either way.
  Kept at 0.5 — raising it would have punished correct answers while
  catching zero of the real errors. This confirmed confidence score
  alone isn't a reliable correctness signal in this dataset, which is
  why the guard's category-match check (§6, rule 3) — not the confidence
  flag — is responsible for catching this class of error.

- **Resolved — pgvector:** not needed. Plain JSON array columns for
  embeddings + Python-side cosine similarity are enough at 50 images.

- **Known limitation, informs guard design:** llava classified fox, dog,
  bear, and deer at 10/10 each, but only 6/10 for wolf (confused with
  fox or dog). This is exactly the failure mode the mismatch guard
  exists to catch — treated as expected, useful eval data rather than a
  bug to fix in Phase 3/4.

- **Still open:** similarity threshold (0.75) is still a starting guess
  — to be tuned against the labeled eval set in Phase 4.