import pandas as pd
import numpy as np
from loguru import logger
from db.database import get_session
from db.models import PriceSnapshot, Product, Retailer
from datetime import datetime, timezone, timedelta


class PriceFeatureEngineer:
    """
    Converts raw price snapshots from PostgreSQL
    into ML-ready features for Prophet and XGBoost.
    """

    def __init__(self):
        self.session = get_session()

    def get_price_history(
        self,
        product_id: int = None,
        retailer_name: str = None,
        days: int = 90
    ) -> pd.DataFrame:
        """
        Fetch price history from PostgreSQL.
        Returns DataFrame with columns: ds, y, product_id, title
        ds = datestamp (Prophet requirement)
        y  = price (Prophet requirement)
        """
        query = self.session.query(
            PriceSnapshot.price,
            PriceSnapshot.scraped_at,
            PriceSnapshot.product_id,
            Product.title,
            Retailer.name.label("retailer"),
        ).join(
            Product, PriceSnapshot.product_id == Product.id
        ).join(
            Retailer, PriceSnapshot.retailer_id == Retailer.id
        )

        # Filter by product
        if product_id:
            query = query.filter(
                PriceSnapshot.product_id == product_id
            )

        # Filter by retailer
        if retailer_name:
            query = query.filter(Retailer.name == retailer_name)

        # Filter by date range
        since = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(PriceSnapshot.scraped_at >= since)

        # Order by time
        query = query.order_by(PriceSnapshot.scraped_at.asc())

        results = query.all()

        if not results:
            logger.warning(
                f"No price history found for "
                f"product_id={product_id}"
            )
            return pd.DataFrame()

        df = pd.DataFrame([{
            "ds": r.scraped_at,
            "y": float(r.price),
            "product_id": r.product_id,
            "title": r.title,
            "retailer": r.retailer,
        } for r in results])

        # Prophet needs timezone-naive timestamps
        df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)

        logger.info(
            f"Loaded {len(df)} price snapshots "
            f"for {df['title'].iloc[0][:40] if len(df) > 0 else 'unknown'}"
        )
        return df

    def get_all_products_history(
        self,
        min_snapshots: int = 2,
        retailer_name: str = None
    ) -> pd.DataFrame:
        """
        Get price history for ALL products.
        Filters out products with too few snapshots.
        """
        query = self.session.query(
            PriceSnapshot.price,
            PriceSnapshot.scraped_at,
            PriceSnapshot.product_id,
            Product.title,
            Retailer.name.label("retailer"),
        ).join(
            Product, PriceSnapshot.product_id == Product.id
        ).join(
            Retailer, PriceSnapshot.retailer_id == Retailer.id
        ).filter(
            PriceSnapshot.price >= 5000
        ).order_by(
            PriceSnapshot.product_id,
            PriceSnapshot.scraped_at.asc()
        )

        if retailer_name:
            query = query.filter(Retailer.name == retailer_name)

        results = query.all()

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame([{
            "ds": r.scraped_at,
            "y": float(r.price),
            "product_id": r.product_id,
            "title": r.title,
            "retailer": r.retailer,
        } for r in results])

        df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)

        # Filter products with enough snapshots
        snapshot_counts = df.groupby("product_id").size()
        valid_products = snapshot_counts[
            snapshot_counts >= min_snapshots
        ].index
        df = df[df["product_id"].isin(valid_products)]

        logger.info(
            f"Loaded {len(df)} snapshots for "
            f"{df['product_id'].nunique()} products"
        )
        return df

    def engineer_xgboost_features(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Create features for XGBoost price drop classifier.

        Features:
        - price_velocity   → how fast price is changing
        - price_vs_7d_avg  → current vs 7-day average
        - price_vs_30d_avg → current vs 30-day average
        - days_since_drop  → days since last price drop
        - price_range_pct  → (max-min)/max over history
        - hour_of_day      → time patterns
        - day_of_week      → day patterns
        - is_weekend       → weekend effect

        Target:
        - will_drop_24h    → 1 if price dropped in next 24h
        """
        features = []

        for product_id in df["product_id"].unique():
            product_df = df[
                df["product_id"] == product_id
            ].copy().sort_values("ds")

            if len(product_df) < 2:
                continue

            for i in range(1, len(product_df)):
                current = product_df.iloc[i]
                history = product_df.iloc[:i]

                # Current price
                current_price = current["y"]

                # Price velocity — change from previous
                prev_price = product_df.iloc[i-1]["y"]
                velocity = (current_price - prev_price) / prev_price

                # vs 7-day average
                week_ago = current["ds"] - pd.Timedelta(days=7)
                week_history = history[history["ds"] >= week_ago]
                avg_7d = (
                    week_history["y"].mean()
                    if len(week_history) > 0
                    else current_price
                )
                vs_7d = (current_price - avg_7d) / avg_7d

                # vs 30-day average
                month_ago = current["ds"] - pd.Timedelta(days=30)
                month_history = history[history["ds"] >= month_ago]
                avg_30d = (
                    month_history["y"].mean()
                    if len(month_history) > 0
                    else current_price
                )
                vs_30d = (current_price - avg_30d) / avg_30d

                # Days since last price drop
                price_drops = history[history["y"] < history["y"].shift(1)]
                if len(price_drops) > 0:
                    last_drop = price_drops["ds"].iloc[-1]
                    days_since_drop = (
                        current["ds"] - last_drop
                    ).total_seconds() / 86400
                else:
                    days_since_drop = 999

                # Price range percentage
                price_range_pct = (
                    (history["y"].max() - history["y"].min())
                    / history["y"].max()
                    if history["y"].max() > 0
                    else 0
                )

                # Time features
                hour = current["ds"].hour
                day_of_week = current["ds"].dayofweek
                is_weekend = 1 if day_of_week >= 5 else 0

                # Target — did price drop in next snapshot?
                next_idx = i + 1
                if next_idx < len(product_df):
                    next_price = product_df.iloc[next_idx]["y"]
                    will_drop = 1 if next_price < current_price else 0
                else:
                    continue  # Skip last row — no future to compare

                features.append({
                    "product_id": product_id,
                    "title": current["title"],
                    "retailer": current["retailer"],
                    "ds": current["ds"],
                    "current_price": current_price,
                    "price_velocity": velocity,
                    "vs_7d_avg": vs_7d,
                    "vs_30d_avg": vs_30d,
                    "days_since_drop": min(days_since_drop, 999),
                    "price_range_pct": price_range_pct,
                    "hour_of_day": hour,
                    "day_of_week": day_of_week,
                    "is_weekend": is_weekend,
                    "will_drop_24h": will_drop,
                })

        feature_df = pd.DataFrame(features)
        logger.info(
            f"Engineered {len(feature_df)} feature rows "
            f"from {df['product_id'].nunique()} products"
        )
        return feature_df

    def close(self):
        self.session.close()