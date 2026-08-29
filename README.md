# AI Image Understanding & Content Matching Engine

FlyRank Internship · Backend Track Capstone

Given a blog post, this system finds the best-matching image from a small
library — or honestly says no image is good enough. A wolf photo on a fox
article gets caught and rejected with a clear reason, not silently returned.

Repo: https://github.com/fatimIB/flyrank-capstone-image-relevance

---

## What it does

1. A vision model looks at every image and produces structured tags
   (subject, category, attributes, caption, confidence) — validated,
   never trusted blindly.
2. Images and blog posts are turned into embeddings and compared by
   semantic similarity, not keyword matching.
3. The top-ranked candidate passes through a **mismatch guard** — three
   independent checks (confidence, similarity, category) — before it's
   ever suggested.
4. Every suggestion (accepted or rejected) is saved, and a human can
   approve or override it through a Review API.
5. A small labeled eval set measures real accuracy against ground truth.

## Architecture

```
Images (imgs/<category>/)
       │
       ▼
  Vision model (Ollama + llava)
       │  validated via Pydantic
       ▼
  image_metadata (subject, category, attributes, caption, confidence)
       │
       ▼
  Embedding model (sentence-transformers)
       │
       ▼                                    Posts (seeded)
  image_embeddings                                │
       │                                          ▼
       │                                    post_embeddings
       │                                          │
       └──────────────► cosine similarity ◄───────┘
                                │
                                ▼
                    rank candidates, take top-1
                                │
                                ▼
                        Mismatch guard
              (confidence → similarity → category)
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
                ACCEPT                   REJECT
                    │                  (with reason)
                    └───────────┬───────────┘
                                ▼
                    Suggestion saved (suggestions table)
                                │
                                ▼
                  Review API (approve / reject / inspect)
```

**Layers:** `app/models/` (schema + persistence) → `app/services/`
(vision, embeddings, matching, guard) → `app/jobs/` (batch scripts) →
`app/routes/` (HTTP API) → `app/main.py` (wiring only).

Full design rationale, every decision, and every number behind it: **[docs/Design.md](docs/Design.md)**.

## Stack

- **Vision:** Ollama + llava (local, no API key, no rate limits)
- **Embeddings:** sentence-transformers (`all-MiniLM-L6-v2`, local)
- **Backend:** FastAPI + SQLAlchemy
- **Database:** SQLite (see [note below](#why-sqlite-instead-of-postgresdocker))
- **Testing:** pytest

---

## Setup

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally

### 1. Clone the repo

```bash
git clone https://github.com/fatimIB/flyrank-capstone-image-relevance.git
cd flyrank-capstone-image-relevance
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Pull the vision model

```bash
ollama pull llava
```

This is a ~4.5GB download and only needs to happen once.

### 4. Set up environment variables

```bash
cp .env.example .env
```

No API keys are needed — everything runs locally. `.env` just sets the
model name and database path.

### 5. Seed the data (run once)

```bash
python -m app.jobs.process_images
python -m app.jobs.seed_posts
python -m app.jobs.generate_embeddings
python -m app.services.matching_engine
```

**Heads up:** `process_images` sends all 50 images through the local
vision model — this takes roughly **90 minutes** on typical hardware.
It prints progress per image; this is expected, not a hang.

### 6. Run the API

```bash
uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs

---

## Trying it out

```bash
# Get an image suggestion for a post (creates + saves a Suggestion)
curl http://localhost:8000/posts/1/images

# Inspect a suggestion in full
curl http://localhost:8000/suggestions/1

# Human review: approve or reject
curl -X POST http://localhost:8000/suggestions/1/approve
curl -X POST http://localhost:8000/suggestions/1/reject
```

## Running the tests

```bash
pytest
```

13 tests across the three required categories, plus one standalone
semantic-matching test:

| File | Covers | Result |
|---|---|---|
| `tests/test_schema.py` | Schema validation | 9/9 passing |
| `tests/test_guard.py` | Mismatch rejection | 1/1 passing |
| `tests/test_matching.py` | Matching accuracy | 3/3 passing |
| `tests/test_semantic_synonym.py` | Semantic matching on equivalent concepts | 1/1 passing (see caveat below) |

Full test output: **[EVIDENCE.md](EVIDENCE.md)**.

## Running the evaluation

```bash
python -m app.jobs.run_eval
```

Measures top-1 precision by comparing each suggestion's image against
its **ground-truth folder category** (never seen by the vision model) —
not the model's own claim, since that would be circular with what the
guard already checks.

**Result: 80% top-1 precision (4/5)**, plus one correctly-identified
"no confident match" case (Roman aqueducts post), reported separately.

---

## Key decisions and findings

*(Full reasoning and raw output for all of these: [docs/Design.md](docs/Design.md), [EVIDENCE.md](EVIDENCE.md), [BUILDLOG.md](BUILDLOG.md))*

### Why Ollama instead of Gemini
Started with Gemini Flash per the suggested stack. The initially-targeted
model was deprecated mid-project, and the replacement's free-tier quota
(20 requests/day) wasn't enough to process 50 images reliably. Switched
to a fully local model — no rate limits, no cost, no external dependency.

### Why the similarity threshold is 0.4, not 0.75
0.75 (the original guess) rejected every single real match — posts are
long essay-style paragraphs while image captions are short visual
descriptions, so even correct matches only scored 0.45–0.70. 0.4 was
chosen because it sits comfortably above the one genuine non-match
(0.059) and below every real match observed.

### The guard's real limitation — and why human review exists
The vision model misclassified some wolf photos with high confidence
(one at 1.00). The guard can only compare what the model *claims*
against what a post *expects* — it can't independently verify ground
truth. This was observed twice, independently: a wolf mislabeled "dog"
(accepted by the guard, then caught and overridden via the Review API),
and a wolf mislabeled "fox" (surfaced by the semantic-matching test).
This is exactly why human review exists as a separate, non-redundant
layer, not a limitation to hide.

### Why no image is currently flagged `needs_review`
The 0.75 confidence threshold was considered against 0.5 using real data:
raising it would have flagged two *correct* answers while catching zero
of the real misclassification errors (which all sat at 0.80–1.00
confidence). The flagging mechanism itself is tested and proven correct
(`test_schema.py`) — none of the 50 images in this dataset happened to
fall below 0.5, which is a property of the data, not a gap in the logic.

### Why SQLite instead of Postgres/Docker
The brief suggests Postgres via Docker as one option. At this scale (50
images, single local demo, no concurrent writes), SQLite is a legitimate
substitution — zero setup, same SQLAlchemy models would work unchanged
against Postgres if `DATABASE_URL` were swapped.

### Cost tracking is real, but always $0
Every vision and embedding call is logged (`ai_usage_log`) with
operation, model, status, and cost — the mechanism is real and would
populate actual costs if swapped to a paid API. No spending cap was
implemented since there's no real spending to cap while running locally.

---

## Known limitations (stated plainly)

- The mismatch guard cannot catch a vision-model error that's internally
  consistent (wrong category *and* a caption that agrees with that wrong
  category) — only human review can. This happened twice in this dataset.
- The similarity threshold (0.4) is tuned for this specific dataset's
  writing style (long posts vs. short captions), not a general-purpose value.
- The semantic-matching test (`test_semantic_synonym.py`) proves the
  *mechanism* works, but its passing result happens to rely on an image
  the vision model itself misclassified — see the test's evidence for
  the full, honest account.
- No cap on AI spending, since actual spending is always $0 locally.

## Submission pack

- `README.md` — this file
- `capstone.yaml` — run/seed/test commands, endpoints
- `EVIDENCE.md` — one real, pasted proof per requirement
- `BUILDLOG.md` — full AI-assisted development log, decisions and reasoning
- `.env.example` — required environment variables
- `docs/Design.md` — full architecture and design rationale