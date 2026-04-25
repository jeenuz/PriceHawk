import os
import csv
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from loguru import logger


def clean_price(price_text: str) -> float:
    """Convert price string to float."""
    try:
        cleaned = (
            price_text
            .replace("₹", "")
            .replace(",", "")
            .replace(".", "")
            .replace(" ", "")
            .strip()
        )
        return float(cleaned)
    except ValueError:
        return 0.0


def scrape_amazon_dishwashers(max_pages: int = 2) -> list[dict]:
    """Scrape dishwasher listings from Amazon India."""
    all_products = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', "
            "{get: () => undefined});"
        )

        for page_num in range(1, max_pages + 1):
            url = (
                "https://www.amazon.in/s?k=dishwasher+machine"
                f"&page={page_num}"
            )
            logger.info(f"Scraping page {page_num}: {url}")

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )
                page.wait_for_timeout(3000)

                # Wait for product containers
                try:
                    page.wait_for_selector(
                        "[data-component-type='s-search-result']",
                        timeout=15000
                    )
                    logger.info("Products loaded!")
                except Exception:
                    logger.warning(f"Timeout on page {page_num}")
                    page.screenshot(
                        path=f"data/amazon_debug_p{page_num}.png"
                    )
                    continue

                # Scroll to load all products
                for _ in range(3):
                    page.evaluate(
                        "window.scrollBy(0, window.innerHeight)"
                    )
                    page.wait_for_timeout(1000)

                # Extract products
                products = extract_products(page, page_num)
                all_products.extend(products)
                logger.info(
                    f"Page {page_num}: {len(products)} products found"
                )

                # Polite delay between pages
                page.wait_for_timeout(2000)

            except Exception as e:
                logger.error(f"Error on page {page_num}: {e}")
                continue

        browser.close()

    return all_products


def extract_products(page, page_num: int) -> list[dict]:
    """Extract all products from current page."""
    products = []

    # Get all product containers
    containers = page.query_selector_all(
        "[data-component-type='s-search-result']"
    )
    logger.info(f"Found {len(containers)} product containers")

    for container in containers:
        try:
            product = extract_single_product(container)
            if product:
                products.append(product)
        except Exception as e:
            logger.warning(f"Error extracting product: {e}")
            continue

    return products


def extract_single_product(container) -> dict | None:
    """Extract data from a single product container."""
    try:
        # ASIN — Amazon unique product ID
        asin = container.get_attribute("data-asin")
        if not asin:
            return None

        # Title — inside h2 tag
        title_el = container.query_selector("h2 a span")
        if not title_el:
            title_el = container.query_selector("h2 span")
        if not title_el:
            return None
        title = title_el.inner_text().strip()
        if not title or len(title) < 5:
            return None

        # URL — build from ASIN
        url_el = container.query_selector("h2 a")
        if url_el:
            href = url_el.get_attribute("href") or ""
            if href.startswith("http"):
                url = href
            else:
                url = f"https://www.amazon.in{href}"
        else:
            url = f"https://www.amazon.in/dp/{asin}"

        # Price — try multiple selectors
        price = 0.0

        # Method 1 — span.a-price-whole (most common)
        price_el = container.query_selector("span.a-price-whole")
        if price_el:
            price = clean_price(price_el.inner_text())

        # Method 2 — span.a-offscreen (screen reader price)
        if price == 0.0:
            price_el = container.query_selector("span.a-offscreen")
            if price_el:
                price = clean_price(price_el.inner_text())

        # Skip products with no price
        if price == 0.0:
            return None

        # Original price (before discount)
        original_price = 0.0
        orig_el = container.query_selector(
            "span.a-price.a-text-price span.a-offscreen"
        )
        if orig_el:
            original_price = clean_price(orig_el.inner_text())

        # Calculate discount
        discount_pct = 0.0
        if original_price > price > 0:
            discount_pct = round(
                ((original_price - price) / original_price) * 100,
                1
            )

        # Rating
        rating_el = container.query_selector("span.a-icon-alt")
        rating = (
            rating_el.inner_text().strip()
            if rating_el else ""
        )

        # Rating count
        rating_count_el = container.query_selector(
            "span.a-size-base.s-underline-text"
        )
        rating_count = (
            rating_count_el.inner_text().strip()
            if rating_count_el else ""
        )

        # Availability badge
        badge_el = container.query_selector("span.a-badge-text")
        badge = badge_el.inner_text().strip() if badge_el else ""

        return {
            "title": title,
            "asin": asin,
            "price": price,
            "original_price": original_price,
            "discount_percent": discount_pct,
            "currency": "INR",
            "availability": "In Stock",
            "rating": rating,
            "rating_count": rating_count,
            "badge": badge,
            "url": url,
            "retailer": "amazon.in",
            "category": "dishwasher",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.warning(f"Error in extract_single_product: {e}")
        return None


def save_to_csv(products: list[dict], filename: str):
    """Save products to CSV."""
    if not products:
        logger.warning("No products to save!")
        return None

    os.makedirs("data", exist_ok=True)
    filepath = f"data/{filename}"

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=products[0].keys())
        writer.writeheader()
        writer.writerows(products)

    logger.info(f"Saved {len(products)} products to {filepath}")
    return filepath


if __name__ == "__main__":
    logger.info("Starting Amazon dishwasher scraper...")

    products = scrape_amazon_dishwashers(max_pages=2)

    logger.info(f"Total products: {len(products)}")

    if products:
        print("\n=== SAMPLE PRODUCTS ===")
        for p in products[:5]:
            print(f"Title:    {p['title'][:65]}")
            print(f"ASIN:     {p['asin']}")
            print(f"Price:    ₹{p['price']:,.0f}")
            print(f"Original: ₹{p['original_price']:,.0f}")
            print(f"Discount: {p['discount_percent']}%")
            print(f"Rating:   {p['rating']}")
            print(f"URL:      {p['url'][:60]}...")
            print("---")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = save_to_csv(
            products,
            f"amazon_dishwashers_{timestamp}.csv"
        )
        print(f"\nSaved to: {filepath}")

    else:
        logger.error(
            "No products found! Check screenshots in data/"
        )