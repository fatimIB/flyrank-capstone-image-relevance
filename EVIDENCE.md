# Evidence

One proof per Definition-of-Done checkbox, pasted as I finish each one.

## Vision processing job with structured output validation ✅

Batch job run on full 50-image corpus, all images processed, schema
validation enforced via Pydantic (ImageMetadata):

```
PS C:\Users\hp\Desktop\FlyRank assignment\flyrank-capstone-image-relevance> python -m app.jobs.process_images
Seeding image records from imgs/ folder...
Running vision pipeline...
Found 50 pending images.
Processing pexels-abdullah-dawud-589034626-17093663.jpg ... OK -> fox (0.95)
Processing pexels-brettjordan-13533977.jpg ... OK -> fox (0.80)
Processing pexels-brettjordan-27114104.jpg ... OK -> fox (0.95)
Processing pexels-brettjordan-9643746.jpg ... OK -> fox (1.00)
Processing pexels-introspectivedsgn-9681760.jpg ... OK -> fox (0.85)
Processing pexels-krisztina-csilla-kiss-2157420968-34713957.jpg ... OK -> fox (0.90)
Processing pexels-malcolm-stirling-507886076-32399356.jpg ... OK -> fox (0.90)
Processing pexels-riccardo-vespa-594469796-26843364.jpg ... OK -> fox (0.85)
Processing pexels-tomas-malik-793526-23914490.jpg ... OK -> fox (0.95)
Processing pexels-travelerchitect-27046678.jpg ... OK -> fox (0.80)
Processing pexels-daniel-lengies-173739220-31767241.jpg ... OK -> wolf (0.95)
Processing pexels-dominikrh-35604352.jpg ... OK -> fox (0.90)
Processing pexels-gabriele-brancati-32566116-9455413.jpg ... OK -> wolf (0.90)
Processing pexels-jesus-esteban-san-jose-11194232-27835321.jpg ... OK -> dog (1.00)
Processing pexels-natarajan-m-272680561-12859255.jpg ... OK -> wolf (1.00)
Processing pexels-nicky-15095927.jpg ... OK -> wolf (0.90)
Processing pexels-nihongraphy-22469233-11800382.jpg ... OK -> wolf (0.80)
Processing pexels-rob-bertrand-2148265487-30004291.jpg ... OK -> wolf (0.80)
Processing pexels-sadullah-akkoyun-156394945-12379934.jpg ... OK -> dog (0.90)
Processing pexels-vinod-kumar-774900553-35667607.jpg ... OK -> dog (0.80)
Processing pexels-chirag-captures-1479983956-27075796.jpg ... OK -> dog (0.95)
Processing pexels-chirag-captures-1479983956-27107874.jpg ... OK -> dog (0.90)
Processing pexels-dhruv-khichi-27563587-14264901.jpg ... OK -> dog (0.75)
Processing pexels-hasbi-habibi-2154298419-33205883.jpg ... OK -> dog (0.70)
Processing pexels-hemant-singh-297238136-16629458.jpg ... OK -> dog (0.70)
Processing pexels-kolkatarchobiwala-28962028.jpg ... OK -> dog (0.95)
Processing pexels-rafael-oliveira-2149835472-33633339.jpg ... OK -> dog (0.90)
Processing pexels-rajesh-s-balouria-1289088-17371948.jpg ... OK -> dog (0.80)
Processing pexels-shiro-yasha0_o-2153652841-33723120.jpg ... OK -> dog (0.90)
Processing pexels-soumyadip-adak-398670506-14930773.jpg ... OK -> dog (0.90)
Processing pexels-22731504-19087687.jpg ... OK -> bear (0.95)
Processing pexels-alena-maruk-106558942-14655951.jpg ... OK -> bear (0.85)
Processing pexels-alena-maruk-106558942-14655953.jpg ... OK -> bear (0.95)
Processing pexels-catharina-dahlqvist-2150987538-31451543.jpg ... OK -> bear (0.80)
Processing pexels-emrecan-dora-576914516-34799366.jpg ... OK -> bear (0.90)
Processing pexels-maxime-max-2160523823-38845918.jpg ... OK -> bear (0.80)
Processing pexels-michal-petras-2152077115-38965587.jpg ... OK -> bear (0.85)
Processing pexels-oliver-morgan-media-400577173-18453573.jpg ... OK -> bear (0.80)
Processing pexels-shtefutsa-17646622.jpg ... OK -> bear (0.90)
Processing pexels-venu-korada-1753278737-28635741.jpg ... OK -> bear (0.80)
Processing pexels-239816836-12390174.jpg ... OK -> deer (0.85)
Processing pexels-carolin-wenske-762365559-19781448.jpg ... OK -> deer (0.95)
Processing pexels-carolin-wenske-762365559-21134646.jpg ... OK -> deer (0.90)
Processing pexels-chris-f-38966-37331865.jpg ... OK -> deer (0.90)
Processing pexels-kemal-berkay-dogan-421902900-27294800.jpg ... OK -> deer (0.85)
Processing pexels-lauren-boswell-191857954-18400259.jpg ... OK -> deer (0.90)
Processing pexels-leeloothefirst-5236400.jpg ... OK -> deer (0.85)
Processing pexels-margarita-141441249-28141256.jpg ... OK -> deer (0.90)
Processing pexels-owen-outdoors-409204690-33423295.jpg ... OK -> deer (1.00)
Processing pexels-roshanravi-33079859.jpg ... OK -> deer (0.85)

Done. 50/50 processed, 0 failed.

```

Every response was parsed as JSON and validated against `ImageMetadata`
(subject, category, attributes, caption, confidence) before being stored —
invalid responses would have been retried or marked `failed`, never
silently accepted.

## Batch processing with retries ✅
 
Batch job proved idempotent/resumable: an earlier interrupted run left
43/50 images processed. Re-running the job automatically skipped the
already-processed images and only picked up the remaining `pending` ones
— no duplicate work, no duplicate DB rows. Retry logic (up to 3 attempts
per image, on JSON/validation/network failure) lives in
`vision_service.classify_image`.
 
**Note on this specific evidence:** the retry logic was genuinely
triggered during development, but the terminal output from those runs
wasn't saved before the sessions were closed, so I can't paste the
original logs here. What I can confirm actually happened, based on what
I observed at the time:
 
- An early run crashed immediately with `ValueError: No API key was provided` 
  — a configuration issue (the `.env` file wasn't being
  loaded), not a retry case. No images were processed in this attempt.
- After fixing that, a run against gemini-2.0-flash showed
  `Found 50 pending images` followed by `FAILED after retries` on the
  images it attempted, which I stopped partway through. I separately checked Google's own site and found gemini-2.0-flash had been deprecated and shut down (June 1, 2026), which explains why calls to it were failing. 
- After switching to gemini-3.5-flash, a later run showed
  `Found 43 pending images` instead of 50 — meaning some images had
  already been marked `processed` or `failed` in the DB from the
  earlier attempt, and the batch job correctly skipped those rather
  than reprocessing them.
- While working with gemini-3.5-flash, I checked my project's actual
  quota in AI Studio and found a real limit of 20 requests/day, which
  wouldn't be enough to reliably finish all 50 images. I decided to
  switch to a fully local model (Ollama + llava) instead of continuing
  to work around Gemini's limits.
- I deleted the SQLite DB file (`capstone.db`) to start clean, and
  re-ran the batch job from scratch against llava — this is the run
  shown in full above: 50/50 processed, 0 failed, no retries needed
  since every local call succeeded on the first attempt.
I don't have an exact, verified account of precisely which images were
marked `processed` vs `failed` between the first two Gemini attempts,
since that terminal output wasn't saved — the summary above only
includes what I directly observed and remember with confidence.
 
The retry mechanism itself is real, in the code, and was exercised
during steps 1–2 above — I just don't have the original terminal capture
of that specific output. The 43/50 resume behavior (proving the
idempotency half of this requirement) is something I do remember
precisely, though I don't have the exact pasted log for it either since
it happened in that same lost terminal session.
 

## Cost tracking per call ✅

Every vision call, success or failure, is logged to `ai_usage_log`:

```
1  vision  llava  1  success  0.0  2026-08-22 19:34:55
2  vision  llava  2  success  0.0  2026-08-22 19:37:09
...
50 vision  llava  50 success  0.0  2026-08-22 21:06:21
```

50 rows, one per image, all attributed with operation/model/status/cost
(local model — cost is $0, but every call is still logged).

## Real classification results (fox/wolf/dog/bear/deer, 50 images)

- fox: 10/10 correct
- wolf: 6/10 correct, 4 misclassified as fox/dog (confidences 0.80–1.00
  on the wrong answers — see BUILDLOG.md, this became an important
  finding about why the guard's category check matters, not just
  confidence thresholds)
- dog: 10/10 correct
- bear: 10/10 correct
- deer: 10/10 correct

Overall raw vision accuracy: 46/50 (92%) — note this is *raw* accuracy,
not the guard's final decision accuracy, which will be measured
separately once the guard is built (Phase 3/4).