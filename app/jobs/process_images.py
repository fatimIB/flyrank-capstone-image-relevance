"""
Batch job — processes every image in imgs/<category>/ through the vision
pipeline. Designed to be safe to re-run: already-processed images are
skipped (idempotency), so a crash halfway through doesn't cost you
duplicate API calls or duplicate DB rows.

Run directly: python -m app.jobs.process_images
"""

import os
from pathlib import Path

from app.models.database import get_session, init_db
from app.models.db_models import Image, ImageMetadataRow, AIUsageLog
from app.services.vision_service import classify_image

IMAGES_ROOT = Path("imgs")
CATEGORIES = ["fox", "wolf", "dog", "bear", "deer"]


def ensure_images_seeded(session):
    """
    Scans imgs/<category>/ and makes sure every file on disk has a
    corresponding 'images' row with status='pending'. Safe to re-run —
    only inserts images that aren't already in the DB.
    """
    existing_filenames = {row.filename for row in session.query(Image).all()}

    for category in CATEGORIES:
        folder = IMAGES_ROOT / category
        if not folder.exists():
            print(f"  ! folder missing: {folder}")
            continue

        for file in sorted(folder.iterdir()):
            if file.name in existing_filenames:
                continue
            session.add(Image(
                filename=file.name,
                folder_category=category,
                status="pending",
            ))
    session.commit()


def process_pending_images(session):
    """
    The core loop: for every image not yet processed, call the vision
    model, validate, store. Skips images already marked 'processed' —
    this is what makes the job idempotent / resumable.
    """
    pending = session.query(Image).filter(Image.status == "pending").all()
    print(f"Found {len(pending)} pending images.")

    for image in pending:
        image_path = str(IMAGES_ROOT / image.folder_category / image.filename)
        print(f"Processing {image.filename} ...", end=" ")

        metadata, cost_entry = classify_image(image_path)

        # Log the AI call regardless of success/failure — cost tracking
        # needs a full record, not just successes.
        session.add(AIUsageLog(
            operation=cost_entry["operation"],
            model=cost_entry["model"],
            reference_id=image.id,
            status=cost_entry["status"],
            estimated_cost=cost_entry["estimated_cost"],
        ))

        if metadata is None:
            image.status = "failed"
            print(f"FAILED after retries. Reason: {cost_entry.get('error')}")
            session.commit()
            continue

        session.add(ImageMetadataRow(
            image_id=image.id,
            subject=metadata.subject,
            category=metadata.category,
            attributes=metadata.attributes,
            caption=metadata.caption,
            confidence=metadata.confidence,
            needs_review=int(metadata.needs_review),
        ))
        image.status = "processed"
        session.commit()

        flag = " [LOW CONFIDENCE - flagged]" if metadata.needs_review else ""
        print(f"OK -> {metadata.category} ({metadata.confidence:.2f}){flag}")


def run():
    init_db()
    session = get_session()
    try:
        print("Seeding image records from imgs/ folder...")
        ensure_images_seeded(session)

        print("Running vision pipeline...")
        process_pending_images(session)

        total = session.query(Image).count()
        processed = session.query(Image).filter(Image.status == "processed").count()
        failed = session.query(Image).filter(Image.status == "failed").count()
        print(f"\nDone. {processed}/{total} processed, {failed} failed.")
    finally:
        session.close()


if __name__ == "__main__":
    run()