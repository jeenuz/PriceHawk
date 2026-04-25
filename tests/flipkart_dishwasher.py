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
            .replace(" ", "")
            .strip()
        )
        return float(cleaned)
    except ValueError:
        return 0.0


def scrape_flipkart_dishwashers(max_pages: int = 3) -> list[dict]:
    """Scrape dishwasher listings from Flipkart."""
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
                "https://www.flipkart.com/search?q=dishwasher+machine"
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

                # Wait for products to load
                try:
                    page.wait_for_selector(
                        "a.pIpigb",
                        timeout=15000
                    )
                except Exception:
                    logger.warning(f"Timeout on page {page_num}")
                    page.screenshot(
                        path=f"data/flipkart_debug_p{page_num}.png"
                    )
                    continue

                # Scroll to load all products
                for _ in range(3):
                    page.evaluate(
                        "window.scrollBy(0, window.innerHeight)"
                    )
                    page.wait_for_timeout(1000)

                # Extract all product links
                products = extract_products(page, page_num)
                all_products.extend(products)
                logger.info(
                    f"Page {page_num}: {len(products)} products"
                )

                # Polite delay
                page.wait_for_timeout(2000)

            except Exception as e:
                logger.error(f"Error on page {page_num}: {e}")
                continue

        browser.close()

    return all_products


def extract_products(page, page_num: int) -> list[dict]:
    """Extract all products from current page."""
    products = []

    # Get all product links
    product_links = page.query_selector_all("a.pIpigb")
    logger.info(f"Found {len(product_links)} product links")

    # Get all discounted prices
    discounted_prices = page.query_selector_all("div.hZ3P6w")

    # Get all original prices
    original_prices = page.query_selector_all("div.kRYCnD")

    for i, link in enumerate(product_links):
        try:
            # Title from title attribute
            title = link.get_attribute("title")
            if not title:
                continue

            # URL
            href = link.get_attribute("href")
            if href:
                if href.startswith("http"):
                    url = href
                else:
                    url = f"https://www.flipkart.com{href}"
            else:
                continue

            # Price — match by index
            price = 0.0
            original_price = 0.0

            if i < len(discounted_prices):
                price_text = discounted_prices[i].inner_text()
                price = clean_price(price_text)

            if i < len(original_prices):
                orig_text = original_prices[i].inner_text()
                original_price = clean_price(orig_text)

            # Skip if no price found
            if price == 0.0:
                continue

            # Calculate discount
            discount_pct = 0.0
            if original_price > 0 and price < original_price:
                discount_pct = round(
                    ((original_price - price) / original_price) * 100,
                    1
                )

            product = {
                "title": title,
                "price": price,
                "original_price": original_price,
                "discount_percent": discount_pct,
                "currency": "INR",
                "availability": "In Stock",
                "url": url,
                "retailer": "flipkart.com",
                "category": "dishwasher",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }

            products.append(product)

        except Exception as e:
            logger.warning(f"Error extracting product {i}: {e}")
            continue

    return products


def save_to_csv(products: list[dict], filename: str):
    """Save products to CSV."""
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
    return filepath


if __name__ == "__main__":
    logger.info("Starting Flipkart dishwasher scraper...")

    products = scrape_flipkart_dishwashers(max_pages=2)

    logger.info(f"Total products: {len(products)}")

    if products:
        print("\n=== SAMPLE PRODUCTS ===")
        for p in products[:5]:
            print(f"Title:     {p['title'][:60]}")
            print(f"Price:     ₹{p['price']:,.0f}")
            print(f"Original:  ₹{p['original_price']:,.0f}")
            print(f"Discount:  {p['discount_percent']}%")
            print(f"URL:       {p['url'][:60]}...")
            print("---")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = save_to_csv(
            products,
            f"flipkart_dishwashers_{timestamp}.csv"
        )
        print(f"\nSaved to: {filepath}")
    else:
        logger.error("No products found! Check screenshots in data/")