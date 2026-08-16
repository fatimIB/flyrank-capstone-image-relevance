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