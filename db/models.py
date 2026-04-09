from sqlalchemy import (
    Column, String, Float, Integer,
    DateTime, ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func
import uuid


class Base(DeclarativeBase):
    pass


class Retailer(Base):
    """Represents an e-commerce site we scrape from."""
    __tablename__ = "retailers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    base_url = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    price_snapshots = relationship("PriceSnapshot", back_populates="retailer")

    def __repr__(self):
        return f"<Retailer(name={self.name})>"


class Product(Base):
    """Represents a unique product tracked across retailers."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    url = Column(Text, nullable=False)
    retailer_id = Column(Integer, ForeignKey("retailers.id"), nullable=False)
    rating = Column(String(10), default="0/5")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Unique constraint — same URL shouldn't be two products
    __table_args__ = (
        UniqueConstraint("url", name="uq_product_url"),
    )

    # Relationships
    price_snapshots = relationship("PriceSnapshot", back_populates="product")

    def __repr__(self):
        return f"<Product(title={self.title[:30]})>"


class PriceSnapshot(Base):
    """
    Every time we scrape a price, one row is added here.
    This gives us full price history for every product.
    """
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    retailer_id = Column(Integer, ForeignKey("retailers.id"), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="GBP")
    availability = Column(String(100), default="")
    content_hash = Column(String(64), nullable=False)  # SHA-256 dedup
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    product = relationship("Product", back_populates="price_snapshots")
    retailer = relationship("Retailer", back_populates="price_snapshots")

    def __repr__(self):
        return f"<PriceSnapshot(price={self.price}, scraped_at={self.scraped_at})>"