from loguru import logger
from db.database import get_session
from db.models import Product
from models.product_matcher import ProductMatcher


class ProductMatchingService:
    """
    Service that uses ProductMatcher to find and link
    duplicate products across retailers in the database.
    """

    def __init__(self):
        self.matcher = ProductMatcher()
        self.session = get_session()

    def find_duplicates_in_db(self) -> list[dict]:
        """
        Scan all products in DB and find potential duplicates
        across different retailers.
        """
        products = self.session.query(Product).all()
        logger.info(f"Scanning {len(products)} products for duplicates...")

        duplicates = []
        checked = set()

        for i, product_a in enumerate(products):
            for j, product_b in enumerate(products):
                if i >= j:
                    continue

                # Skip if same retailer
                if product_a.retailer_id == product_b.retailer_id:
                    continue

                # Skip if already checked this pair
                pair_key = tuple(sorted([product_a.id, product_b.id]))
                if pair_key in checked:
                    continue
                checked.add(pair_key)

                # Compare titles
                result = self.matcher.combined_score(
                    product_a.title,
                    product_b.title
                )

                if result["is_match"]:
                    duplicates.append({
                        "product_a": {
                            "id": product_a.id,
                            "title": product_a.title,
                            "retailer_id": product_a.retailer_id,
                        },
                        "product_b": {
                            "id": product_b.id,
                            "title": product_b.title,
                            "retailer_id": product_b.retailer_id,
                        },
                        "match_result": result,
                    })
                    logger.info(
                        f"Match found! {product_a.title[:30]} "
                        f"≈ {product_b.title[:30]} "
                        f"(score: {result['combined_score']})"
                    )

        logger.info(f"Found {len(duplicates)} potential duplicates")
        return duplicates

    def match_new_product(self, title: str, retailer_id: int) -> dict:
        """
        When a new product is scraped, check if it already
        exists in DB under a different retailer.
        """
        # Get all products from OTHER retailers
        existing_products = self.session.query(Product).filter(
            Product.retailer_id != retailer_id
        ).all()

        if not existing_products:
            return {"matched": False, "reason": "no products from other retailers"}

        candidate_titles = [p.title for p in existing_products]

        # Find best match
        result = self.matcher.find_best_match(title, candidate_titles)

        if result["is_match"]:
            matched_product = existing_products[result["match_index"]]
            return {
                "matched": True,
                "matched_product_id": matched_product.id,
                "matched_title": matched_product.title,
                "score": result["score"],
                "confidence": result["confidence"],
                "needs_review": result["confidence"] == "medium",
            }

        return {
            "matched": False,
            "best_score": result["score"],
            "reason": "no match above threshold",
        }

    def close(self):
        self.session.close()