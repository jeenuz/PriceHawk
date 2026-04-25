import json
import csv
import os
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from loguru import logger


def scrape_myntra_smartphones(max_pages: int = 2) -> list[dict]:
    """
    Scrape smartphone listings from Myntra using Playwright.
    Returns list of product dicts.
    """
    products = []

    with sync_playwright() as p:
        # Launch browser
        # headless=True  → invisible (production)
        # headless=False → visible (development/debugging)
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )

        # Create context with realistic settings
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )

        page = context.new_page()

        # Hide webdriver flag — tells site this is not a bot
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        for page_num in range(1, max_pages + 1):
            url = (
                f"https://www.myntra.com/smartphones"
                f"?p={page_num}&sort=popularity"
            )
            logger.info(f"Scraping page {page_num}: {url}")

            try:
                # Go to page
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Wait for products to load
                try:
                    page.wait_for_selector(
                        ".product-base",
                        timeout=15000
                    )
                    logger.info("Products loaded!")
                except Exception:
                    logger.warning("Timeout waiting for products")
                    # Take screenshot to debug
                    page.screenshot(
                        path=f"data/myntra_debug_p{page_num}.png"
                    )
                    continue

                # Scroll down to load lazy images
                for _ in range(3):
                    page.evaluate(
                        "window.scrollBy(0, window.innerHeight)"
                    )
                    page.wait_for_timeout(1000)

                # Scroll back to top
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(500)

                # Extract products
                page_products = extract_products(page, page_num)
                products.extend(page_products)
                logger.info(
                    f"Page {page_num}: extracted {len(page_products)} products"
                )

                # Polite delay between pages
                page.wait_for_timeout(2000)

            except Exception as e:
                logger.error(f"Error on page {page_num}: {e}")
                page.screenshot(
                    path=f"data/myntra_error_p{page_num}.png"
                )
                continue

        browser.close()

    return products


def extract_products(page, page_num: int) -> list[dict]:
    """Extract all products from current page."""
    products = []

    # Get all product cards
    product_cards = page.query_selector_all(".product-base")
    logger.info(f"Found {len(product_cards)} product cards")

    for card in product_cards:
        try:
            product = extract_single_product(card, page)
            if product:
                products.append(product)
        except Exception as e:
            logger.warning(f"Error extracting product: {e}")
            continue

    return products


def extract_single_product(card, page) -> dict | None:
    """Extract data from a single product card."""
    try:
        # Brand name
        brand_el = card.query_selector(".product-brand")
        brand = brand_el.inner_text().strip() if brand_el else ""

        # Product name
        name_el = card.query_selector(".product-product")
        name = name_el.inner_text().strip() if name_el else ""

        # Full title = brand + name
        title = f"{brand} {name}".strip()
        if not title:
            return None

        # Discounted price (current price)
        price_el = card.query_selector(".product-discountedPrice")
        if not price_el:
            # Try original price if no discount
            price_el = card.query_selector(".product-price")
        price_text = price_el.inner_text().strip() if price_el else "0"
        price = clean_price(price_text)

        # Original price (before discount)
        original_el = card.query_selector(".product-strike")
        original_price_text = (
            original_el.inner_text().strip() if original_el else price_text
        )
        original_price = clean_price(original_price_text)

        # Discount percentage
        discount_el = card.query_selector(".product-discountPercentage")
        discount = (
            discount_el.inner_text().strip() if discount_el else "0% off"
        )

        # Product URL
        link_el = card.query_selector("a")
        href = link_el.get_attribute("href") if link_el else ""
        url = (
            f"https://www.myntra.com{href}"
            if href and not href.startswith("http")
            else href
        )

        # Rating
        rating_el = card.query_selector(".product-ratingsCount")
        rating = rating_el.inner_text().strip() if rating_el else ""

        return {
            "title": title,
            "brand": brand,
            "price": price,
            "original_price": original_price,
            "discount": discount,
            "currency": "INR",
            "availability": "In Stock",
            "rating": rating,
            "url": url,
            "retailer": "myntra.com",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.warning(f"Error in extract_single_product: {e}")
        return None


def clean_price(price_text: str) -> float:
    """Convert price string to float."""
    try:
        # Remove ₹, commas, spaces
        cleaned = (
            price_text
            .replace("₹", "")
            .replace(",", "")
            .replace(" ", "")
            .strip()
        )
        return float(cleaned)
    except ValueError:
        return 0.0


def save_to_csv(products: list[dict], filename: str):
    """Save products to CSV file."""
    if not products:
        logger.warning("No products to save!")
        return

    os.makedirs("data", exist_ok=True)
    filepath = f"data/{filename}"

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=products[0].keys())
        writer.writeheader()
        writer.writerows(products)

    logger.info(f"Saved {len(products)} products to {filepath}")


if __name__ == "__main__":
    logger.info("Starting Myntra scraper...")

    products = scrape_myntra_smartphones(max_pages=2)

    logger.info(f"Total products scraped: {len(products)}")

    if products:
        # Show first 3 products
        print("\n--- Sample products ---")
        for p in products[:3]:
            print(f"Title:    {p['title']}")
            print(f"Price:    ₹{p['price']}")
            print(f"Discount: {p['discount']}")
            print(f"URL:      {p['url'][:60]}...")
            print("---")

        # Save to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_to_csv(products, f"myntra_{timestamp}.csv")
    else:
        logger.warning(
            "No products found! Check screenshots in data/ folder"
        )