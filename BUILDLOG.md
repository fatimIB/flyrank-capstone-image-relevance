## Phase 1 — Design

- Used AI to think through the database design. Went back and forth on 
  whether `approvals` should be its own table — decided to merge it into 
  `suggestions` as a `human_decision` column instead, since a separate 
  table felt like unnecessary complexity at my scale (50 images).

- AI suggested keeping `subject` (free text) and `category` (controlled 
  label) as separate fields in image_metadata, so the model's raw answer 
  can be compared against my folder-based ground truth later during eval. 
  Made sense, kept it.

- Guard rule order (confidence check → similarity check → category check) 
  was proposed by AI. I initially didn't understand why confidence gets 
  checked first, before similarity — realized it's because a low-confidence 
  tag makes everything downstream unreliable, so there's no point checking 
  similarity/category on data you don't trust yet.

- Similarity threshold set to 0.75 as a placeholder. This is a guess, not 
  measured — flagged as an open question in docs/Design.md. Will revisit 
  once I have real eval data in Phase 4.

- Chose fox/wolf/dog/bear/deer categories directly from the brief's own 
  example (§7) rather than inventing my own, since the demo script and 
  probes are written around this exact fox-vs-wolf confusion case.

## Phase 2 — Vision pipeline

- I asked Claude (AI) to write the vision pipeline code based on the
  design from Phase 1: `app/services/vision_service.py`,
  `app/jobs/process_images.py`, `app/models/database.py`, and the
  SQLAlchemy tables in `app/models/db_models.py`. **The AI wrote the
  actual code in these files — I did not write it line by line myself.**
  My role was directing what it needed to do,
  testing it against real data, catching bugs, and deciding what to keep
  or change based on results. I read through each file to understand
  what it does before running it, since I'm expected to be able to
  explain any line of it.

- First implementation used Gemini Flash (google-genai SDK), per the
  brief's suggested stack. I hit two real blockers running it myself:
  (1) the model name AI initially used, gemini-2.0-flash, turned out to
  be deprecated — Google shut it down June 1 2026. I caught this myself
  from a warning message and told the AI, which corrected it to
  gemini-3.5-flash. (2) After switching models, I checked my actual
  quota directly in AI Studio and found my real free-tier
  limit was only 20 requests/day — not enough to reliably process 50
  images without risking a mid-run failure.

- Given the 20 RPD ceiling and my one-week deadline, I decided to switch
  to a fully local model via Ollama instead of continuing to work around
  Gemini's limits. I already had Ollama installed (with gemma3:1b, a
  text-only model). I pulled `llava` (~4.5GB) after an initial download
  attempt failed with a network error and a retry succeeded. I asked the
  AI to rewrite vision_service.py to call Ollama locally instead of
  Gemini — no API key, no rate limits.

- Before trusting the local model's output, I wanted to personally verify
  it was actually looking at image content and not just reading category
  info from my folder names (my images are organized as imgs/fox/,
  imgs/wolf/, etc.). I ran a first test myself: copied a deer photo into
  the fox/ folder and asked the model what it saw. It said "fox" — which
  matched the folder name, so I was still genuinely unsure whether it
  had actually looked at the image or just echoed the folder. The AI
  traced through the code with me and pointed out image_path is only
  used to load file bytes via the `images=` parameter and is never
  inserted into the text prompt — so path-reading shouldn't be
  structurally possible — but I wanted to check it myself with a
  cleaner test rather than just take that explanation on faith.

- I used a small standalone script (test_vision.py) and ran two
  images moved to my Desktop, completely outside any category folder,
  with filenames containing no animal-related words at all. With zero
  folder or filename hints available, the model still correctly
  described a white dog in one image and a fawn/deer in the other. This
  was a cleaner test than my first one and gave me real confidence the
  pipeline is doing genuine vision, not reading paths.

- Ran the full batch job on all 50 images myself: 50/50 processed, 0
  crashes. Partway through an earlier run, I noticed it had only found
  43 pending images instead of 50 so earlier interrupted run had
  already marked some images `processed`, and the batch job correctly
  skipped them on resume rather than reprocessing (proving the
  idempotency the AI had built in actually works, not just in theory).

- Looking at the real results myself, I noticed wolf photos were
  misclassified 4/10 times (as fox or dog) — including one case with
  confidence 1.00 that was wrong. I raised this myself and asked whether
  it was a bug. The AI's explanation was that this is a real visual
  similarity limitation (wolves resembling both foxes and dogs
  depending on the photo), not a code bug — I accepted this because the
  errors were isolated to wolf specifically and every other category
  was 10/10 correct, which fits that explanation better than a code bug
  would.

- The AI suggested raising the needs_review confidence threshold from
  0.5 to 0.75, reasoning it would catch more uncertain cases. I checked
  this against my actual data myself before agreeing to the change: the
  two rows that would newly get flagged at 0.75 were both CORRECT
  answers (0.7-confidence puppy photos), while every actual wolf
  misclassification sat at 0.8-1.00 confidence and would still pass
  through unflagged either way. I pointed this out and decided to keep
  the threshold at 0.5 — raising it would have punished correct answers
  while catching zero of the real errors. This showed that confidence alone could not reliably detect the observed wolf errors. The category-match guard can catch cases where the model's
  claimed category conflicts with the post's expected category, but it cannot
  catch a confidently misclassified image when the model's incorrect category
  already agrees with the post. That limitation became an important Phase 3
  finding.

## Phase 3 — Matching engine (in progress)

- I asked the AI to write the embedding and matching code:
  `app/jobs/seed_posts.py`, `app/services/embedding_service.py`,
  `app/services/similarity.py`, `app/jobs/generate_embeddings.py`, and
  `app/services/matching_engine.py`. **The AI wrote this code, not me.**
  My role was running it, reading it to understand it, and testing it
  against my real data.

- Ran `generate_embeddings.py` on all 50 images and 6 posts — worked
  cleanly, no errors, using `sentence-transformers` (`all-MiniLM-L6-v2`)
  locally, same library I already knew from AskFatima.

- First test of the full matching engine, using the 0.75 threshold from
  my Phase 1 design, rejected all 6 posts — including the 5 real,
  correctly-topical ones. I noticed this myself and questioned it rather
  than assuming the threshold was correct just because AI had suggested
  it originally.

- I asked the AI to explain why real matches were only scoring
  0.45-0.70 instead of something closer to 1.0. The explanation: my
  posts are long, essay-style paragraphs (behavior, history, ecology)
  while my image captions are short, plain visual descriptions — these
  are structurally different types of text, so even a correct semantic
  match won't score near-identical. I found this explanation checks out
  against my own data: the true non-match (Roman aqueducts post) scored
  0.059, a huge, clean gap below every real match (0.45-0.70) — proving
  the embeddings themselves are working correctly, it's specifically my
  threshold guess from Phase 1 that didn't hold up against real data.

- Separately, I noticed something concerning myself while reading the
  Post 3 (dog post) result: the top-ranked candidate was image_id=19,
  which I recognized from my Phase 2 data as one of the wolf photos the
  vision model had mislabeled as "dog." I raised this directly: if I
  lower the threshold so this candidate actually gets accepted, the
  guard's category check would see category="dog" matching the dog
  post's expected_category="dog" and pass it — recommending an actual
  wolf photo as a dog image, with the guard finding nothing wrong.

- I pushed on this with the AI and confirmed it's a real, structural
  limitation: the guard can only compare what the vision model *claims*
  (category) against what the post expects — it has no independent way
  to verify the model's claim is actually true. When the model is
  wrong but internally consistent (wrong category AND a caption that
  matches that wrong category), nothing in the guard's current design
  can catch it. This is different from the fox/wolf case the guard DOES
  catch, where the model's stated category itself disagrees with the
  post — this case has no such disagreement to detect.

- I decided not to try to "fix" this by having the guard secretly check
  against my folder_category ground truth, since a real system
  wouldn't have that available for new, unlabeled images — that would
  make the guard only work on my own test data, not represent a real
  solution. Instead, documenting it honestly as a known limitation in
  Design.md and EVIDENCE.md, and relying on the human review layer
  (Phase 4) as the intended mechanism for catching exactly this class
  of error — which is why review exists as a separate layer, not a
  redundant one.

- I then directly questioned why the threshold should stay at 0.75
  "until Phase 4 eval" when the data I already had made it obviously
  unusable — every real post was being rejected, which isn't a case of
  fine-tuning, it's a broken default. I pushed for changing it now
  rather than waiting. Looking at my own numbers (real matches at
  0.45-0.70, true non-match at 0.059), I picked 0.4 as the new value —
  comfortably above the non-match, comfortably below the weakest real
  match, both grounded in my own observed data rather than a round
  guess.

- Re-ran the matching engine with the threshold at 0.4: all 5 real
  posts now ACCEPTED with images from their own category; the Roman
  aqueducts post still correctly REJECTED (similarity 0.059, nowhere
  close to 0.4). This confirmed §12 Probe 4 ("no confident match") is
  working. It also confirmed the limitation I found earlier was real,
  not just theoretical — image_id=19 (the mislabeled wolf-as-dog photo)
  is now genuinely accepted as the dog post's top match, exactly as
  predicted.

- Still outstanding: none of the 6 posts triggered an actual
  category-mismatch REJECTION from the guard (rule 3), since each
  post's top candidate already happened to share its category. Probe 3
  ("force the wolf as a candidate for the fox post → guard rejects it")
  still needs to be tested explicitly, not just inferred from these 6
  runs.