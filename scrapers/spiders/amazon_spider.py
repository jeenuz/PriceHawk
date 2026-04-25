import scrapy
from scrapy_playwright.page import PageMethod
from loguru import logger
from scrapers.items import PriceItem
from scrapers.proxy_manager import ProxyManager
from datetime import datetime, timezone


class AmazonSpider(scrapy.Spider):
    name = "amazon"
    retailer_name = "amazon.in"

    SEARCH_QUERIES = [
        "dishwasher+machine",
        "washing+machine",
        "refrigerator",
    ]

    MAX_PAGES = 2

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapers.middlewares.useragent.RotateUserAgentMiddleware": None,
        },
        "DOWNLOAD_DELAY": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 1,
    }

    DESKTOP_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy_manager = ProxyManager()

    def start_requests(self):
        for query in self.SEARCH_QUERIES:
            for page_num in range(1, self.MAX_PAGES + 1):
                url = (
                    f"https://www.amazon.in/s"
                    f"?k={query}&page={page_num}"
                )

                # Get a proxy for this request
                proxy = self.proxy_manager.get_playwright_proxy()

                if proxy:
                    logger.info(f"Using proxy: {proxy['server']}")
                else:
                    logger.warning("No proxy — trying direct connection")

                # Build context kwargs
                context_kwargs = {
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": self.DESKTOP_UA,
                    "locale": "en-IN",
                    "timezone_id": "Asia/Kolkata",
                    "extra_http_headers": {
                        "Accept-Language": "en-IN,en;q=0.9",
                    }
                }

                # Add proxy if available
                if proxy:
                    context_kwargs["proxy"] = proxy

                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta={
                        "playwright": True,
                        "playwright_context_kwargs": context_kwargs,
                        "playwright_page_methods": [
                            PageMethod(
                                "add_init_script",
                                """
                                Object.defineProperty(
                                    navigator, 'webdriver',
                                    {get: () => undefined}
                                );
                                window.chrome = {runtime: {}};
                                """
                            ),
                            PageMethod(
                                "wait_for_load_state",
                                "domcontentloaded"
                            ),
                            PageMethod("wait_for_timeout", 4000),
                            PageMethod(
                                "screenshot",
                                path="data/amazon_proxy_check.png"
                            ),
                            PageMethod(
                                "wait_for_selector",
                                "[data-component-type='s-search-result']",
                                timeout=20000
                            ),
                            PageMethod(
                                "evaluate",
                                "window.scrollBy(0, window.innerHeight)"
                            ),
                            PageMethod("wait_for_timeout", 2000),
                            PageMethod(
                                "evaluate",
                                "window.scrollBy(0, window.innerHeight)"
                            ),
                            PageMethod("wait_for_timeout", 1500),
                        ],
                        "playwright_include_page": True,
                        # Store proxy so errback can mark it failed
                        "proxy": proxy["server"] if proxy else None,
                    },
                    errback=self.errback,
                )

    async def parse(self, response):
        """Extract products from Amazon search results."""
        page = response.meta.get("playwright_page")
        proxy = response.meta.get("proxy")

        try:
            logger.info(f"Parsing: {response.url}")
            if proxy:
                logger.info(f"Via proxy: {proxy}")

            # Check if rate limited or CAPTCHA
            page_check = await page.evaluate("""
                () => ({
                    title: document.title,
                    is_blocked: document.body.innerText.includes('Oops')
                        || document.body.innerText.includes('captcha')
                        || document.body.innerText.includes('CAPTCHA')
                        || document.body.innerText.includes('robot')
                        || document.body.innerText.includes('rush hour'),
                    product_count: document.querySelectorAll(
                        '[data-component-type="s-search-result"]'
                    ).length
                })
            """)

            logger.info(f"Page title: {page_check['title']}")
            logger.info(f"Products found: {page_check['product_count']}")

            if page_check["is_blocked"]:
                logger.warning(
                    f"Blocked on proxy {proxy}! "
                    f"Marking as failed."
                )
                if proxy:
                    self.proxy_manager.mark_failed(proxy)
                return

            # Mark proxy as successful
            if proxy:
                self.proxy_manager.mark_success(proxy)

            # Extract all product data
            products_data = await page.evaluate("""
                () => {
                    var containers = document.querySelectorAll(
                        '[data-component-type="s-search-result"]'
                    );
                    var results = [];
                    for (var i = 0; i < containers.length; i++) {
                        var c = containers[i];
                        var asin = c.getAttribute('data-asin');
                        if (!asin || asin === '') continue;

                        var titleEl = c.querySelector('h2 a span');
                        if (!titleEl) {
                            titleEl = c.querySelector(
                                'h2 span.a-text-normal'
                            );
                        }
                        var title = titleEl
                            ? titleEl.textContent.trim() : '';
                        if (!title || title.length < 5) continue;

                        var hrefEl = c.querySelector('h2 a');
                        var href = hrefEl
                            ? hrefEl.getAttribute('href') : '';

                        var priceEl = c.querySelector(
                            'span.a-price-whole'
                        );
                        var priceText = priceEl
                            ? priceEl.textContent.trim() : '';

                        if (!priceText) {
                            var offEl = c.querySelector(
                                'span.a-offscreen'
                            );
                            priceText = offEl
                                ? offEl.textContent.trim() : '0';
                        }

                        var ratingEl = c.querySelector(
                            'span.a-icon-alt'
                        );
                        var rating = ratingEl
                            ? ratingEl.textContent.trim() : '';

                        results.push({
                            asin: asin,
                            title: title,
                            href: href,
                            price_text: priceText,
                            rating: rating
                        });
                    }
                    return results;
                }
            """)

            logger.info(f"Extracted {len(products_data)} products")

            for product in products_data:
                try:
                    price = self._clean_price(product["price_text"])
                    if price < 5000:
                        continue

                    href = product["href"]
                    if href and href.startswith("http"):
                        url = href
                    elif href:
                        url = f"https://www.amazon.in{href}"
                    else:
                        url = (
                            f"https://www.amazon.in/dp/"
                            f"{product['asin']}"
                        )

                    item = PriceItem(
                        title=product["title"],
                        price=price,
                        currency="INR",
                        availability="In Stock",
                        rating=product["rating"],
                        url=url,
                        retailer="amazon.in",
                        scraped_at=datetime.now(
                            timezone.utc
                        ).isoformat(),
                    )

                    logger.info(
                        f"Saved: {product['title'][:40]} "
                        f"— ₹{price:,.0f}"
                    )
                    yield item.to_dict()

                except Exception as e:
                    logger.warning(f"Product error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Parse error: {e}")
            if proxy:
                self.proxy_manager.mark_failed(proxy)

        finally:
            if page:
                await page.close()

    async def errback(self, failure):
        """Handle failed requests — mark proxy as failed."""
        page = failure.request.meta.get("playwright_page")
        proxy = failure.request.meta.get("proxy")

        if proxy:
            logger.warning(f"Request failed via proxy {proxy}")
            self.proxy_manager.mark_failed(proxy)

        if page:
            try:
                await page.screenshot(
                    path="data/amazon_proxy_error.png"
                )
            except Exception:
                pass
            await page.close()

        logger.error(
            f"Failed: {failure.request.url} "
            f"— {failure.value}"
        )

    def _clean_price(self, price_text: str) -> float:
        try:
            cleaned = (
                price_text
                .replace("₹", "")
                .replace(",", "")
                .replace(" ", "")
                .strip()
                .rstrip(".")
            )
            return float(cleaned)
        except ValueError:
            return 0.0