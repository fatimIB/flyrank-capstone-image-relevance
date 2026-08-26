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
`needs_review` instead of being trusted automatically. (0.75 was
considered as an alternative and checked against the real confidence
values already in the data — see §8 for the reasoning; kept at 0.5.)

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

2. similarity >= threshold (0.4 — see below for how this was set) ?
   NO  → REJECT: "no confident match, similarity below threshold"

3. image.category == post.expected_category ?
   NO  → REJECT: "category mismatch: expected {expected}, detected {actual}"
   YES → ACCEPT
```
The confidence check is a safety filter, not a correctness guarantee.
The observed evaluation showed that the model can assign high confidence
to incorrect classifications, so passing the confidence check does not mean
the image classification is correct.

Each post is manually tagged with an `expected_category` at creation time
(e.g. the fox test post is tagged `fox`) — this keeps rule 3 simple,
instead of inferring topic from free text.

Rejections always return a `reason` string — never just `false`.

**Similarity threshold:** set to 0.4 for this evaluation dataset after
observing the initial 0.75 threshold reject every real match. The observed
scores ranged from 0.45–0.70 for the five topical posts and 0.059 for the
unrelated post. Therefore 0.4 separates the observed non-match from the
observed positive matches. This is a dataset-specific threshold, not a
production-calibrated value; broader evaluation would be needed before
treating it as a general threshold.

**Known limitation:** the guard only verifies *consistency* between what
the vision model claims (category) and what the post expects — it
cannot independently confirm the model's claim is actually true. If the
model is confidently and consistently wrong (wrong category AND a
caption matching that wrong category), the guard has no signal to catch
it — this can't be fixed inside the guard without giving it access to
ground truth a real system wouldn't have for new images. This is why
human review (`human_decision` on `suggestions`) exists as a separate
layer, not a redundant one. See EVIDENCE.md/BUILDLOG.md for the specific
case this was observed in.

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
value (currently $0 across the board, since llava and the embedding
model both run locally).

**Indexes:** foreign key columns (`image_id`, `post_id` on the embedding
and suggestion tables) are indexed to keep lookups fast when ranking
candidates for a post. `images.status` is indexed since the batch job
filters on it every run (`WHERE status = 'pending'`).

## 8. Open questions / resolved findings

- **Resolved — confidence threshold for `needs_review`:** kept at 0.5.
  Considered raising to 0.75 and checked it against the real confidence
  values already in the data (not a live re-run): it would have flagged
  two correct answers while catching zero of the real misclassification
  errors. Confidence score alone isn't a reliable correctness signal in
  this dataset — full reasoning in BUILDLOG.md.

- **Resolved — pgvector:** not needed. Plain JSON array columns for
  embeddings + Python-side cosine similarity are enough at 50 images.

- **Resolved — similarity threshold:** changed from 0.75 to 0.4 based on
  real test results — see §6.

- **Resolved — Probe 3:** tested explicitly with `tests/test_guard.py`
  — a correctly-labeled wolf image forced onto the fox post is rejected
  by rule 3 with a category-mismatch reason, even though its similarity
  score (0.410) alone would have cleared the threshold. Full test
  output in EVIDENCE.md.