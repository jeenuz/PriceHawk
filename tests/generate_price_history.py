"""
Generates synthetic price history for ML training.
Based on real scraped prices with realistic fluctuations.
Used for testing ML pipeline before real history accumulates.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import numpy as np
from datetime import datetime, timezone, timedelta
from loguru import logger
from db.database import get_session, init_db
from db.models import Product, Retailer, PriceSnapshot
import hashlib
import json


def generate_realistic_price_history(
    base_price: float,
    days: int = 90,
    volatility: float = 0.03,
) -> list[dict]:
    """
    Generate realistic price history for a product.

    Simulates:
    - Small daily fluctuations (±1-2%)
    - Occasional bigger drops (sales events)
    - Price recovery after drops
    - Weekend pricing patterns
    """
    prices = []
    current_price = base_price
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    for day in range(days):
        date = start_date + timedelta(days=day)

        # Weekend effect — slightly higher prices
        if date.weekday() >= 5:
            weekend_factor = random.uniform(1.0, 1.02)
        else:
            weekend_factor = random.uniform(0.99, 1.01)

        # Random sale events (5% chance per day)
        if random.random() < 0.05:
            sale_factor = random.uniform(0.85, 0.95)
        else:
            sale_factor = 1.0

        # Simulate Big Billion Day (October) and Diwali
        if date.month == 10 and 8 <= date.day <= 15:
            sale_factor = random.uniform(0.75, 0.88)

        # Daily random fluctuation
        daily_change = random.gauss(0, volatility)

        # Apply all factors
        new_price = current_price * (
            1 + daily_change
        ) * weekend_factor * sale_factor

        # Round to nearest 10 (realistic for Indian prices)
        new_price = round(new_price / 10) * 10

        # Keep price within 30% of base
        new_price = max(base_price * 0.70, new_price)
        new_price = min(base_price * 1.30, new_price)

        prices.append({
            "price": new_price,
            "date": date,
        })

        # Price recovery — slowly move back toward base
        current_price = (current_price * 0.95) + (new_price * 0.05)

    return prices


def populate_price_history(days: int = 90):
    """
    Add synthetic price history to all products in DB.
    """
    init_db()
    session = get_session()

    try:
        # Get all products with their current prices
        products = session.query(Product).all()
        logger.info(f"Found {len(products)} products")

        total_saved = 0
        total_skipped = 0

        for product in products:
            # Get current price from latest snapshot
            latest = session.query(PriceSnapshot).filter_by(
                product_id=product.id
            ).order_by(
                PriceSnapshot.scraped_at.desc()
            ).first()

            if not latest or latest.price < 5000:
                continue

            base_price = latest.price
            retailer_id = latest.retailer_id

            logger.info(
                f"Generating history for: "
                f"{product.title[:45]} "
                f"(₹{base_price:,.0f})"
            )

            # Generate price history
            history = generate_realistic_price_history(
                base_price=base_price,
                days=days,
                volatility=0.025,
            )

            for entry in history:
                # Generate hash for deduplication
                content = json.dumps({
                    "url": product.url,
                    "price": entry["price"],
                    "availability": "In Stock",
                }, sort_keys=True)
                content_hash = hashlib.sha256(
                    content.encode()
                ).hexdigest()

                # Check duplicate
                existing = session.query(PriceSnapshot).filter_by(
                    product_id=product.id,
                    content_hash=content_hash
                ).first()

                if existing:
                    total_skipped += 1
                    continue

                snapshot = PriceSnapshot(
                    product_id=product.id,
                    retailer_id=retailer_id,
                    price=entry["price"],
                    currency=latest.currency,
                    availability="In Stock",
                    content_hash=content_hash,
                    scraped_at=entry["date"],
                )
                session.add(snapshot)
                total_saved += 1

            session.commit()

        logger.info(f"Saved {total_saved} synthetic snapshots")
        logger.info(f"Skipped {total_skipped} duplicates")

        # Verify
        total = session.query(PriceSnapshot).count()
        logger.info(f"Total snapshots in DB: {total}")

    except Exception as e:
        session.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logger.info("Generating synthetic price history...")
    logger.info(
        "Note: This simulates 90 days of price changes "
        "for ML training. Real history will replace this "
        "as your scheduler runs daily."
    )
    populate_price_history(days=90)
    logger.info("Done!")