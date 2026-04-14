import hashlib
import json
from loguru import logger
from db.database import get_session, init_db
from db.models import Product, Retailer, PriceSnapshot
from models.product_matcher import ProductMatcher


class PostgreSQLPipeline:
    """Saves scraped price data to PostgreSQL."""

    def open_spider(self, spider):
        """Called when spider starts — set up DB connection."""
        init_db()
        self.session = get_session()
        self._ensure_retailer(spider)
        self.matcher = ProductMatcher()
        logger.info("PostgreSQL pipeline opened.")

    def close_spider(self, spider):
        """Called when spider finishes — close DB connection."""
        self.session.close()
        logger.info("PostgreSQL pipeline closed.")

    def process_item(self, item, spider):
        """Called for every scraped item — save to DB."""
        try:
            product = self._get_or_create_product(item)
            content_hash = self._generate_hash(item)

            existing = self.session.query(PriceSnapshot).filter_by(
                product_id=product.id,
                content_hash=content_hash
            ).first()

            if existing:
                logger.debug(f"Skipping duplicate: {item['title'][:40]}")
                return item

            snapshot = PriceSnapshot(
                product_id=product.id,
                retailer_id=self.retailer.id,
                price=item["price"],
                currency=item.get("currency", "GBP"),
                availability=item.get("availability", ""),
                content_hash=content_hash,
            )
            self.session.add(snapshot)
            self.session.commit()
            logger.info(f"Saved: {item['title'][:40]} — £{item['price']}")

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving item: {e}")

        return item

    def _ensure_retailer(self, spider):
        """Get or create retailer record."""
        retailer_name = getattr(spider, "retailer_name", "books.toscrape.com")
        self.retailer = self.session.query(Retailer).filter_by(
            name=retailer_name
        ).first()

        if not self.retailer:
            self.retailer = Retailer(
                name=retailer_name,
                base_url=f"http://{retailer_name}",
            )
            self.session.add(self.retailer)
            self.session.commit()
            logger.info(f"Created retailer: {retailer_name}")

    def _get_or_create_product(self, item):
        """
        Get existing product or create new one.
        Uses ProductMatcher to find same product
        across different retailers.
        """
        # Step 1 — check by exact URL first (fastest)
        product = self.session.query(Product).filter_by(
            url=item["url"]
        ).first()

        if product:
            return product

        # Step 2 — check for matching product from other retailers
        existing_products = self.session.query(Product).filter(
            Product.retailer_id != self.retailer.id
        ).all()

        if existing_products:
            candidate_titles = [p.title for p in existing_products]

            result = self.matcher.find_best_match(
                item["title"],
                candidate_titles
            )

            # High confidence match — link to existing product
            if result["is_match"] and result["confidence"] == "high":
                matched = existing_products[result["match_index"]]
                logger.info(
                    f"Cross-retailer match: "
                    f"{item['title'][:30]} "
                    f"≈ {matched.title[:30]} "
                    f"(score: {result['score']})"
                )
                return matched

        # Step 3 — no match found, create new product
        product = Product(
            title=item["title"],
            url=item["url"],
            retailer_id=self.retailer.id,
            rating=item.get("rating", "0/5"),
        )
        self.session.add(product)
        self.session.commit()
        return product

    def _generate_hash(self, item) -> str:
        """Generate SHA-256 hash for deduplication."""
        content = json.dumps({
            "url": item["url"],
            "price": item["price"],
            "availability": item["availability"],
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()