"""
Evaluation script — measures top-1 precision: of all posts with a real
expected image category, what fraction did the system correctly match?

Critically, this compares the suggested image's GROUND-TRUTH category
(image.folder_category — the folder it was sourced into, which the
vision model never sees) against the post's expected_category. This is
deliberately NOT the same check the guard performs (which only compares
the model's own CLAIMED category against the post) — using ground truth
here is what makes this a genuine, independent measurement rather than
circular re-checking of the guard's own logic.

Posts with expected_category="none" (no real matching image exists,
e.g. the Roman aqueducts post) are excluded from the precision
denominator and reported separately, since "correct" for them means
"correctly rejected," not "correctly matched to an image."

Run: python -m app.jobs.run_eval
"""

from app.models.database import get_session
from app.models.db_models import Post, Suggestion, Image


def run_eval():
    session = get_session()
    try:
        posts = session.query(Post).all()
        if not posts:
            print("No posts found — run `python -m app.jobs.seed_posts` first.")
            return

        scored_results = []       # posts with a real expected_category
        no_match_results = []     # posts with expected_category == "none"

        for post in posts:
            # Use the most recent suggestion for this post
            suggestion = (
                session.query(Suggestion)
                .filter(Suggestion.post_id == post.id)
                .order_by(Suggestion.id.desc())
                .first()
            )
            if suggestion is None:
                print(f"  (skipping post {post.id} — no suggestion found, run matching_engine first)")
                continue

            if post.expected_category == "none":
                # This post has no correct image — success means the
                # system rejected it (status == "rejected")
                correctly_rejected = suggestion.status == "rejected"
                no_match_results.append((post, suggestion, correctly_rejected))
                continue

            # Normal post — check ground truth, not the model's claim
            is_correct = False
            actual_category = None
            if suggestion.image_id is not None:
                image = session.query(Image).filter(Image.id == suggestion.image_id).first()
                if image is not None:
                    actual_category = image.folder_category
                    is_correct = (
                        suggestion.status == "accepted"
                        and actual_category == post.expected_category
                    )

            scored_results.append((post, suggestion, actual_category, is_correct))

        # --- Report ---
        print("=" * 70)
        print("EVALUATION — Top-1 Precision")
        print("=" * 70)

        for post, suggestion, actual_category, is_correct in scored_results:
            mark = "CORRECT" if is_correct else "WRONG"
            print(
                f"Post {post.id} ({post.title}) [expected: {post.expected_category}]\n"
                f"  suggestion: image_id={suggestion.image_id} "
                f"(ground truth category: {actual_category}), status={suggestion.status}\n"
                f"  -> {mark}\n"
            )

        for post, suggestion, correctly_rejected in no_match_results:
            mark = "CORRECT (no-match case)" if correctly_rejected else "WRONG (should have rejected)"
            print(
                f"Post {post.id} ({post.title}) [expected: none — no real match exists]\n"
                f"  suggestion status={suggestion.status}, reason: {suggestion.reason}\n"
                f"  -> {mark}\n"
            )

        correct_count = sum(1 for *_, is_correct in scored_results if is_correct)
        total_scored = len(scored_results)
        precision = (correct_count / total_scored * 100) if total_scored else 0.0

        print("=" * 70)
        print(f"Top-1 precision: {correct_count}/{total_scored} = {precision:.1f}%")
        print(f"(excludes {len(no_match_results)} no-match post(s), reported separately above)")
        print("=" * 70)

        return precision

    finally:
        session.close()


if __name__ == "__main__":
    run_eval()