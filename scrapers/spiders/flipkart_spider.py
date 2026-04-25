import scrapy
from scrapy_playwright.page import PageMethod
from loguru import logger
from scrapers.items import PriceItem
from datetime import datetime, timezone


class FlipkartSpider(scrapy.Spider):
    name = "flipkart"
    retailer_name = "flipkart.com"

    # Search queries to scrape
    SEARCH_QUERIES = [
        "dishwasher+machine",
        #"washing+machine",
        #"refrigerator",
    ]

    MAX_PAGES = 3

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
    }

    def start_requests(self):
        """Generate requests for all search queries."""
        for query in self.SEARCH_QUERIES:
            for page_num in range(1, self.MAX_PAGES + 1):
                url = (
                    f"https://www.flipkart.com/search"
                    f"?q={query}&page={page_num}"
                )
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta={
                        "playwright": True,
                        "playwright_context": "flipkart",
                        "playwright_context_kwargs": {
                            "viewport": {
                                "width": 1920,
                                "height": 1080
                            },
                            "user_agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                                " AppleWebKit/537.36 (KHTML, like Gecko)"
                                " Chrome/120.0.0.0 Safari/537.36"
                            ),
                            "locale": "en-IN",
                            "timezone_id": "Asia/Kolkata",
                        },
                        "playwright_page_methods": [
                            # Hide webdriver
                            PageMethod(
                                "add_init_script",
                                "Object.defineProperty(navigator,"
                                "'webdriver',{get:()=>undefined});"
                            ),
                            # Wait for products
                            PageMethod(
                                "wait_for_selector",
                                "a.pIpigb",
                                timeout=15000
                            ),
                            # Scroll to load all
                            PageMethod(
                                "evaluate",
                                "window.scrollBy(0, window.innerHeight)"
                            ),
                            PageMethod("wait_for_timeout", 1500),
                            PageMethod(
                                "evaluate",
                                "window.scrollBy(0, window.innerHeight)"
                            ),
                            PageMethod("wait_for_timeout", 1000),
                        ],
                        "playwright_include_page": True,
                    },
                    errback=self.errback,
                )

    async def parse(self, response):
        """Extract products from Flipkart search results."""
        page = response.meta.get("playwright_page")

        try:
            logger.info(f"Parsing Flipkart: {response.url}")

            # Get all product links
            product_links = await page.query_selector_all("a.pIpigb")

            # Get prices
            discounted = await page.query_selector_all("div.hZ3P6w")
            original = await page.query_selector_all("div.kRYCnD")

            logger.info(f"Found {len(product_links)} products")

            for i, link in enumerate(product_links):
                try:
                    title = await link.get_attribute("title")
                    if not title:
                        continue

                    href = await link.get_attribute("href")
                    if not href:
                        continue

                    url = (
                        f"https://www.flipkart.com/{href.lstrip('/')}"
                        if not href.startswith("http")
                        else href
                    )

                    # Get price
                    price = 0.0
                    if i < len(discounted):
                        price_text = await discounted[i].inner_text()
                        price = self._clean_price(price_text)

                    # Skip accessories (< ₹5000)
                    if price < 5000:
                        continue

                    # Get original price
                    original_price = 0.0
                    if i < len(original):
                        orig_text = await original[i].inner_text()
                        original_price = self._clean_price(orig_text)

                    # Calculate discount
                    discount = 0.0
                    if original_price > price > 0:
                        discount = round(
                            ((original_price - price) / original_price)
                            * 100, 1
                        )

                    item = PriceItem(
                        title=title,
                        price=price,
                        currency="INR",
                        availability="In Stock",
                        rating="",
                        url=url,
                        retailer="flipkart.com",
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    )

                    yield item.to_dict()

                except Exception as e:
                    logger.warning(f"Error extracting product {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing page: {e}")

        finally:
            await page.close()

    async def errback(self, failure):
        """Handle request errors."""
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
        logger.error(f"Request failed: {failure.request.url}")

    def _clean_price(self, price_text: str) -> float:
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