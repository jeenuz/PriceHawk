import sys
import os
import csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.product_matcher import ProductMatcher
from loguru import logger


def load_csv(filepath: str) -> list[dict]:
    products = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(row)
    return products


def filter_machines_only(products: list[dict]) -> list[dict]:
    filtered = []
    for p in products:
        try:
            price = float(p.get("price", 0))
            if price >= 5000:
                filtered.append(p)
        except ValueError:
            continue
    return filtered


def match_across_retailers(
    amazon_products: list[dict],
    flipkart_products: list[dict],
    matcher: ProductMatcher
) -> list[dict]:
    matches = []
    flipkart_titles = [p["title"] for p in flipkart_products]

    logger.info(
        f"Matching {len(amazon_products)} Amazon products "
        f"against {len(flipkart_products)} Flipkart products..."
    )

    for amazon_product in amazon_products:
        amazon_title = amazon_product["title"]
        result = matcher.find_best_match(amazon_title, flipkart_titles)

        if result["is_match"]:
            flipkart_product = flipkart_products[result["match_index"]]
            amazon_price = float(amazon_product["price"])
            flipkart_price = float(flipkart_product["price"])

            if amazon_price < flipkart_price:
                cheaper = "Amazon"
                saving = flipkart_price - amazon_price
            elif flipkart_price < amazon_price:
                cheaper = "Flipkart"
                saving = amazon_price - flipkart_price
            else:
                cheaper = "Same price"
                saving = 0

            match = {
                "amazon_title": amazon_title[:80],
                "flipkart_title": flipkart_product["title"][:80],
                "amazon_price": amazon_price,
                "flipkart_price": flipkart_price,
                "match_score": result["score"],
                "confidence": result["confidence"],
                "cheaper_on": cheaper,
                "saving": round(saving, 2),
                "amazon_url": amazon_product["url"],
                "flipkart_url": flipkart_product["url"],
            }
            matches.append(match)

            logger.info(
                f"MATCH [{result['confidence']}] "
                f"score={result['score']} | "
                f"Amazon ₹{amazon_price:,.0f} vs "
                f"Flipkart ₹{flipkart_price:,.0f} | "
                f"Cheaper: {cheaper} "
                f"(save ₹{saving:,.0f})"
            )

    return matches


def print_matches(matches: list[dict]):
    if not matches:
        print("\nNo matches found!")
        return

    print(f"\n{'='*70}")
    print(f"FOUND {len(matches)} MATCHING PRODUCTS ACROSS AMAZON & FLIPKART")
    print(f"{'='*70}")

    for i, match in enumerate(matches, 1):
        print(f"\n--- Match {i} ---")
        print(f"Amazon:   {match['amazon_title'][:65]}")
        print(f"Flipkart: {match['flipkart_title'][:65]}")
        print(f"Score:    {match['match_score']} ({match['confidence']})")
        print(f"Amazon:   ₹{match['amazon_price']:,.0f}")
        print(f"Flipkart: ₹{match['flipkart_price']:,.0f}")
        print(f"Cheaper:  {match['cheaper_on']} "
              f"(save ₹{match['saving']:,.0f})")


def save_matches_csv(matches: list[dict]):
    if not matches:
        return None

    os.makedirs("data", exist_ok=True)
    filepath = "data/dishwasher_price_comparison.csv"

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=matches[0].keys())
        writer.writeheader()
        writer.writerows(matches)

    logger.info(f"Saved comparison to {filepath}")
    return filepath


if __name__ == "__main__":
    data_dir = "data"

    amazon_files = sorted([
        f for f in os.listdir(data_dir)
        if f.startswith("amazon_dishwashers")
    ])
    flipkart_files = sorted([
        f for f in os.listdir(data_dir)
        if f.startswith("flipkart_dishwashers")
    ])

    if not amazon_files:
        logger.error("No Amazon CSV found! Run amazon_dishwasher.py first")
        sys.exit(1)

    if not flipkart_files:
        logger.error("No Flipkart CSV found! Run flipkart_dishwasher.py first")
        sys.exit(1)

    amazon_file = os.path.join(data_dir, amazon_files[-1])
    flipkart_file = os.path.join(data_dir, flipkart_files[-1])

    logger.info(f"Loading Amazon: {amazon_file}")
    logger.info(f"Loading Flipkart: {flipkart_file}")

    amazon_products = load_csv(amazon_file)
    flipkart_products = load_csv(flipkart_file)

    logger.info(f"Amazon total: {len(amazon_products)}")
    logger.info(f"Flipkart total: {len(flipkart_products)}")

    amazon_machines = filter_machines_only(amazon_products)
    flipkart_machines = filter_machines_only(flipkart_products)

    logger.info(f"Amazon machines: {len(amazon_machines)}")
    logger.info(f"Flipkart machines: {len(flipkart_machines)}")

    logger.info("Loading SBERT matcher...")
    matcher = ProductMatcher()

    matches = match_across_retailers(
        amazon_machines,
        flipkart_machines,
        matcher
    )

    print_matches(matches)

    if matches:
        filepath = save_matches_csv(matches)
        print(f"\nSaved to: {filepath}")

        savings = [m["saving"] for m in matches if m["saving"] > 0]
        if savings:
            print(f"\n=== SUMMARY ===")
            print(f"Total matches:       {len(matches)}")
            print(f"Max saving:          ₹{max(savings):,.0f}")
            print(f"Avg saving:          ₹{sum(savings)/len(savings):,.0f}")
            cheaper_amazon = sum(
                1 for m in matches if m["cheaper_on"] == "Amazon"
            )
            cheaper_flipkart = sum(
                1 for m in matches if m["cheaper_on"] == "Flipkart"
            )
            print(f"Cheaper on Amazon:   {cheaper_amazon} products")
            print(f"Cheaper on Flipkart: {cheaper_flipkart} products")