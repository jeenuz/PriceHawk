import scrapy
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceItem:
    """Represents one scraped price record."""
    title: str = ""
    price: float = 0.0
    currency: str = "GBP"
    availability: str = ""
    rating: str = ""
    url: str = ""
    retailer: str = ""
    scraped_at: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "price": self.price,
            "currency": self.currency,
            "availability": self.availability,
            "rating": self.rating,
            "url": self.url,
            "retailer": self.retailer,
            "scraped_at": self.scraped_at,
        }