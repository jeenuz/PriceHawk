"""
Runs pure Playwright scrapers and saves results
to PostgreSQL via Scrapy pipeline.
"""
import sys
import os

# Add project ROOT to path — not scrapers folder
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Add tests folder for playwright scrapers
TESTS_DIR = os.path.join(PROJECT_ROOT, 'tests')
sys.path.insert(0, TESTS_DIR)

from datetime import datetime, timezone
from loguru import logger
from db.database import get_session, init_db
from db.models import Product, Retailer, PriceSnapshot
from models.product_matcher import ProductMatcher
import hashlib
import json

from amazon_dishwasher import scrape_amazon_dishwashers
from flipkart_dishwasher import scrape_flipkart_dishwashers


class DirectPipeline:
    """
    Saves scraped items directly to PostgreSQL.
    Same logic as Scrapy pipeline but runs standalone.
    """

    def __init__(self):
        init_db()
        self.session = get_session()
        self.matcher = ProductMatcher()
        self.stats = {
            "saved": 0,
            "skipped_duplicate": 0,
            "skipped_no_price": 0,
            "errors": 0,
        }
        logger.info("Pipeline initialized")

    def get_or_create_retailer(self, retailer_name: str):
        """Get or create retailer record."""
        retailer = self.session.query(Retailer).filter_by(
            name=retailer_name
        ).first()

        if not retailer:
            retailer = Retailer(
                name=retailer_name,
                base_url=f"https://www.{retailer_name}",
            )
            self.session.add(retailer)
            self.session.commit()
            logger.info(f"Created retailer: {retailer_name}")

        return retailer

    def get_or_create_product(
        self,
        item: dict,
        retailer: Retailer
    ) -> Product:
        """Get existing product or create new one."""
        product = self.session.query(Product).filter_by(
            url=item["url"]
        ).first()

        if product:
            return product

        existing = self.session.query(Product).filter(
            Product.retailer_id != retailer.id
        ).all()

        if existing:
            candidate_titles = [p.title for p in existing]
            result = self.matcher.find_best_match(
                item["title"],
                candidate_titles
            )

            if result["is_match"] and result["confidence"] == "high":
                matched = existing[result["match_index"]]
                logger.info(
                    f"Cross-retailer match: "
                    f"{item['title'][:30]} ≈ "
                    f"{matched.title[:30]} "
                    f"(score: {result['score']})"
                )
                return matched

        # Clean rating — truncate to 50 chars max
        rating = item.get("rating", "0/5")
        if rating and len(rating) > 50:
            rating = rating[:50]

        # Convert "4.6 out of 5 stars" → "4.6/5"
        if "out of" in rating:
            try:
                score = rating.split(" out of ")[0].strip()
                rating = f"{score}/5"
            except Exception:
                rating = "0/5"

        product = Product(
            title=item["title"],
            url=item["url"],
            retailer_id=retailer.id,
            rating=rating,
        )
        self.session.add(product)
        self.session.commit()
        return product

    def generate_hash(self, item: dict) -> str:
        """SHA-256 hash for deduplication."""
        content = json.dumps({
            "url": item["url"],
            "price": item["price"],
            "availability": item.get("availability", ""),
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def save_item(self, item: dict, retailer: Retailer):
        """Save one scraped item to PostgreSQL."""
        try:
            if not item.get("price") or item["price"] == 0:
                self.stats["skipped_no_price"] += 1
                return

            product = self.get_or_create_product(item, retailer)
            content_hash = self.generate_hash(item)

            # Check duplicate
            existing = self.session.query(PriceSnapshot).filter_by(
                product_id=product.id,
                content_hash=content_hash
            ).first()

            if existing:
                self.stats["skipped_duplicate"] += 1
                return

            # Save new snapshot
            snapshot = PriceSnapshot(
                product_id=product.id,
                retailer_id=retailer.id,
                price=item["price"],
                currency=item.get("currency", "INR"),
                availability=item.get("availability", "In Stock"),
                content_hash=content_hash,
            )
            self.session.add(snapshot)
            self.session.commit()

            self.stats["saved"] += 1
            logger.info(
                f"Saved: {item['title'][:45]} "
                f"— ₹{item['price']:,.0f}"
            )

        except Exception as e:
            self.session.rollback()
            self.stats["errors"] += 1
            logger.error(f"Error saving item: {e}")

    def save_all(self, items: list[dict], retailer_name: str):
        """Save all items for a retailer."""
        retailer = self.get_or_create_retailer(retailer_name)
        logger.info(
            f"Saving {len(items)} items "
            f"for {retailer_name}..."
        )

        for item in items:
            self.save_item(item, retailer)

        logger.info(
            f"Done {retailer_name}: "
            f"{self.stats['saved']} saved, "
            f"{self.stats['skipped_duplicate']} duplicates, "
            f"{self.stats['errors']} errors"
        )

    def close(self):
        self.session.close()

    def print_stats(self):
        logger.info("=== Pipeline Stats ===")
        for key, val in self.stats.items():
            logger.info(f"  {key}: {val}")


def run_full_pipeline():
    """Run all scrapers and save to PostgreSQL."""
    pipeline = DirectPipeline()

    try:
        # Step 1 — scrape Flipkart
        logger.info("=" * 50)
        logger.info("STEP 1: Scraping Flipkart...")
        logger.info("=" * 50)
        flipkart_items = scrape_flipkart_dishwashers(max_pages=2)
        logger.info(f"Flipkart: {len(flipkart_items)} items scraped")

        flipkart_machines = [
            i for i in flipkart_items
            if i.get("price", 0) >= 5000
        ]
        logger.info(f"Flipkart machines: {len(flipkart_machines)}")
        pipeline.save_all(flipkart_machines, "flipkart.com")

        # Step 2 — scrape Amazon
        logger.info("=" * 50)
        logger.info("STEP 2: Scraping Amazon...")
        logger.info("=" * 50)
        amazon_items = scrape_amazon_dishwashers(max_pages=2)
        logger.info(f"Amazon: {len(amazon_items)} items scraped")

        amazon_machines = [
            i for i in amazon_items
            if i.get("price", 0) >= 5000
        ]
        logger.info(f"Amazon machines: {len(amazon_machines)}")
        pipeline.save_all(amazon_machines, "amazon.in")

        # Step 3 — print stats
        logger.info("=" * 50)
        logger.info("STEP 3: Pipeline complete!")
        logger.info("=" * 50)
        pipeline.print_stats()

        # Step 4 — verify database
        session = pipeline.session
        total_products = session.query(Product).count()
        total_snapshots = session.query(PriceSnapshot).count()
        logger.info(f"Total products in DB:   {total_products}")
        logger.info(f"Total snapshots in DB:  {total_snapshots}")

    finally:
        pipeline.close()


if __name__ == "__main__":
    logger.info("PriceHawk Direct Pipeline starting...")
    run_full_pipeline()
    logger.info("Done!")