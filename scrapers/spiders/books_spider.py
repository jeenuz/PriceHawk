import scrapy
from datetime import datetime, timezone
from loguru import logger
from scrapers.items import PriceItem


class BooksSpider(scrapy.Spider):
    name = "books"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["http://books.toscrape.com/catalogue/page-1.html"]

    custom_settings = {
        "FEEDS": {
            "data/prices_%(time)s.csv": {
                "format": "csv",
                "overwrite": False
            }
        }
    }

    def parse(self, response):
        """Parse product listings from a catalogue page."""
        books = response.css("article.product_pod")
        logger.info(f"Found {len(books)} books on {response.url}")

        for book in books:
            yield self._parse_book(book, response)

        # Follow next page automatically
        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            next_url = response.urljoin(next_page)
            logger.info(f"Following next page: {next_url}")
            yield scrapy.Request(next_url, callback=self.parse)

    def _parse_book(self, book, response) -> dict:
        """Extract data from a single book element."""
        # Extract raw price string e.g. "£51.77"
        raw_price = book.css("p.price_color::text").get(default="0")
        price = self._clean_price(raw_price)

        # Rating is stored as a word class e.g. "Three"
        rating_word = book.css("p.star-rating::attr(class)").get(default="")
        rating = self._parse_rating(rating_word)

        # Build full URL to product page
        relative_url = book.css("h3 a::attr(href)").get(default="")
        full_url = response.urljoin(relative_url)

        item = PriceItem(
            title=book.css("h3 a::attr(title)").get(default="").strip(),
            price=price,
            currency="GBP",
            availability=" ".join(
            t.strip() for t in book.css("p.instock.availability::text").getall()
            if t.strip()
        ),
            rating=rating,
            url=full_url,
            retailer="books.toscrape.com",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )
        print("availability",item.availability)

        return item.to_dict()

    def _clean_price(self, raw: str) -> float:
        """Strip currency symbols and convert to float."""
        try:
            cleaned = raw.replace("£", "").replace(
                "$", "").replace(",", "").strip()
            return float(cleaned)
        except ValueError:
            logger.warning(f"Could not parse price: {raw}")
            return 0.0

    def _parse_rating(self, class_str: str) -> str:
        """Convert word rating to number e.g. 'Three' -> '3/5'."""
        rating_map = {
            "One": "1/5",
            "Two": "2/5",
            "Three": "3/5",
            "Four": "4/5",
            "Five": "5/5",
        }
        for word, score in rating_map.items():
            if word in class_str:
                return score
        return "0/5"