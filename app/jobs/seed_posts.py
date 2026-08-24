"""
Seed script — creates the small set of test blog posts used to exercise
the matching engine and mismatch guard. Run once (or re-run safely —
it checks for existing posts by title before inserting).

Run: python -m app.jobs.seed_posts
"""

from app.models.database import get_session, init_db
from app.models.db_models import Post

POSTS = [
    {
        "title": "Red Fox Behavior",
        "content": (
            "Red foxes are highly adaptable mammals found across forests, "
            "grasslands, and even urban areas. Known for their reddish-orange "
            "fur, pointed ears, and bushy tail, foxes are solitary hunters "
            "that primarily feed on small rodents, birds, and insects. "
            "Despite their wild nature, red foxes have successfully adapted "
            "to living alongside humans in many parts of the world."
        ),
        "expected_category": "fox",
    },
    {
        "title": "Wolves in the Wild",
        "content": (
            "Gray wolves are apex predators that live and hunt in coordinated "
            "packs, typically led by a breeding pair. Wolves communicate "
            "through howls, body language, and scent marking to maintain "
            "territory and coordinate hunts. Once widespread across North "
            "America and Eurasia, wolf populations have been shaped heavily "
            "by human activity and conservation efforts."
        ),
        "expected_category": "wolf",
    },
    {
        "title": "Understanding Domestic Dogs",
        "content": (
            "Dogs have been companions to humans for thousands of years, "
            "descended from ancestral wolves through domestication. Modern "
            "dog breeds vary enormously in size, temperament, and purpose, "
            "from small lapdogs to large working breeds. Dogs are known for "
            "their loyalty, trainability, and strong social bond with their "
            "human families."
        ),
        "expected_category": "dog",
    },
    {
        "title": "Life of the Brown Bear",
        "content": (
            "Brown bears are large, powerful mammals found in forests and "
            "mountainous regions across the Northern Hemisphere. They are "
            "omnivores, feeding on everything from berries and roots to fish "
            "and small mammals. Brown bears spend much of the colder months "
            "in a state of hibernation, relying on fat reserves built up "
            "during the warmer seasons."
        ),
        "expected_category": "bear",
    },
    {
        "title": "Deer Habitats and Migration",
        "content": (
            "Deer are graceful, herbivorous mammals found in a wide range of "
            "habitats, from dense forests to open grasslands. Many deer "
            "species undergo seasonal migration in search of food and milder "
            "climates. Male deer, or bucks, are known for their impressive "
            "antlers, which they shed and regrow annually."
        ),
        "expected_category": "deer",
    },
    {
        # Deliberately unrelated to any image category — tests the
        # "no confident match" case (brief §12, Probe 4 / §16 example).
        "title": "The Architecture of Ancient Roman Aqueducts",
        "content": (
            "Roman aqueducts were remarkable feats of engineering, designed "
            "to transport fresh water across long distances using gravity "
            "alone. Built from stone, brick, and volcanic cement, many "
            "aqueducts spanned dozens of miles, crossing valleys via arched "
            "bridges. Some Roman aqueducts remained in use for centuries, "
            "a testament to the precision of ancient Roman engineering."
        ),
        "expected_category": "none",  # no real category — should get "no confident match"
    },
]


def run():
    init_db()
    session = get_session()
    try:
        existing_titles = {p.title for p in session.query(Post).all()}

        added = 0
        for post_data in POSTS:
            if post_data["title"] in existing_titles:
                print(f"Skipping (already exists): {post_data['title']}")
                continue

            session.add(Post(
                title=post_data["title"],
                content=post_data["content"],
                expected_category=post_data["expected_category"],
            ))
            added += 1
            print(f"Added: {post_data['title']} (expected: {post_data['expected_category']})")

        session.commit()
        print(f"\nDone. {added} new posts added.")
    finally:
        session.close()


if __name__ == "__main__":
    run()