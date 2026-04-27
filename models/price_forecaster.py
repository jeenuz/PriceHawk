import pandas as pd
import numpy as np
import joblib
import os
from prophet import Prophet
from loguru import logger
from models.feature_engineer import PriceFeatureEngineer


class PriceForecaster:
    """
    Uses Facebook Prophet to forecast product price
    trends over the next 7 days.

    Prophet is perfect for price forecasting because:
    - Handles missing data automatically
    - Captures weekly/monthly seasonality
    - Works well with limited data (even 10 points)
    - Gives confidence intervals (uncertainty bands)
    """

    MODEL_DIR = "models/saved"

    def __init__(self):
        os.makedirs(self.MODEL_DIR, exist_ok=True)

    def train(
        self,
        df: pd.DataFrame,
        product_id: int
    ) -> Prophet:
        """
        Train Prophet model for one product.
        df must have columns: ds (datetime), y (price)
        """
        if len(df) < 2:
            logger.warning(
                f"Not enough data for product {product_id} "
                f"— need at least 2 points, got {len(df)}"
            )
            return None

        logger.info(
            f"Training Prophet for product {product_id} "
            f"with {len(df)} data points..."
        )

        model = Prophet(
            # Price data has no strong yearly seasonality
            yearly_seasonality=False,

            # Weekly patterns — prices often change on weekends
            weekly_seasonality=True,

            # Daily patterns — less relevant for prices
            daily_seasonality=False,

            # How much the trend can change
            # Higher = more flexible trend
            changepoint_prior_scale=0.1,

            # Uncertainty interval width
            interval_width=0.80,
        )

        # Add Indian sale event seasonality
        # Prices drop during these events
        sale_events = pd.DataFrame([
            {
                "holiday": "Diwali_sale",
                "ds": pd.Timestamp("2024-10-25"),
                "lower_window": -7,
                "upper_window": 2,
            },
            {
                "holiday": "Big_Billion_Day",
                "ds": pd.Timestamp("2024-10-10"),
                "lower_window": -3,
                "upper_window": 1,
            },
            {
                "holiday": "Republic_Day_sale",
                "ds": pd.Timestamp("2025-01-20"),
                "lower_window": -3,
                "upper_window": 2,
            },
            {
                "holiday": "Independence_Day_sale",
                "ds": pd.Timestamp("2025-08-10"),
                "lower_window": -3,
                "upper_window": 2,
            },
        ])
        model.holidays = sale_events

        # Fit the model
        model.fit(df[["ds", "y"]])

        logger.info(f"Prophet trained for product {product_id}!")
        return model

    def forecast(
        self,
        model: Prophet,
        periods: int = 7
    ) -> pd.DataFrame:
        """
        Generate price forecast for next N days.
        Returns DataFrame with forecast and confidence intervals.
        """
        # Create future dates
        future = model.make_future_dataframe(
            periods=periods,
            freq="D"
        )

        # Generate forecast
        forecast = model.predict(future)

        # Keep only relevant columns
        result = forecast[[
            "ds",
            "yhat",        # predicted price
            "yhat_lower",  # lower bound (80% confidence)
            "yhat_upper",  # upper bound (80% confidence)
            "trend",       # trend component
        ]].tail(periods)

        return result

    def train_all_products(
        self,
        engineer: PriceFeatureEngineer
    ) -> dict:
        """Train Prophet models for all products."""
        df = engineer.get_all_products_history(min_snapshots=2)

        if df.empty:
            logger.error("No data found!")
            return {}

        models = {}
        product_ids = df["product_id"].unique()

        logger.info(
            f"Training Prophet for {len(product_ids)} products..."
        )

        for product_id in product_ids:
            product_df = df[
                df["product_id"] == product_id
            ][["ds", "y"]].copy()

            model = self.train(product_df, product_id)
            if model:
                models[product_id] = model

                # Save model to disk
                model_path = os.path.join(
                    self.MODEL_DIR,
                    f"prophet_{product_id}.joblib"
                )
                joblib.dump(model, model_path)

        logger.info(
            f"Trained and saved {len(models)} Prophet models"
        )
        return models

    def load_model(self, product_id: int) -> Prophet | None:
        """Load saved Prophet model from disk."""
        model_path = os.path.join(
            self.MODEL_DIR,
            f"prophet_{product_id}.joblib"
        )
        if os.path.exists(model_path):
            return joblib.load(model_path)
        return None

    def predict_product(
        self,
        product_id: int,
        engineer: PriceFeatureEngineer,
        periods: int = 7
    ) -> dict:
        """
        Full prediction pipeline for one product.
        Returns forecast with human-readable summary.
        """
        # Load or train model
        model = self.load_model(product_id)

        if not model:
            df = engineer.get_price_history(product_id=product_id)
            if df.empty:
                return {"error": "No price history found"}
            model = self.train(df, product_id)
            if not model:
                return {"error": "Could not train model"}

        # Generate forecast
        forecast = self.forecast(model, periods=periods)

        # Get current price (last known)
        df = engineer.get_price_history(product_id=product_id)
        current_price = df["y"].iloc[-1] if not df.empty else 0
        title = df["title"].iloc[0] if not df.empty else "Unknown"

        # Predicted price in 7 days
        predicted_price = forecast["yhat"].iloc[-1]
        predicted_low = forecast["yhat_lower"].iloc[-1]
        predicted_high = forecast["yhat_upper"].iloc[-1]

        # Price direction
        change = predicted_price - current_price
        change_pct = (change / current_price) * 100

        if change_pct < -2:
            direction = "DOWN"
            advice = "Wait — price likely to drop!"
        elif change_pct > 2:
            direction = "UP"
            advice = "Buy now — price likely to rise!"
        else:
            direction = "STABLE"
            advice = "Price stable — buy when convenient"

        return {
            "product_id": product_id,
            "title": title,
            "current_price": round(current_price, 2),
            "predicted_price_7d": round(predicted_price, 2),
            "predicted_low": round(predicted_low, 2),
            "predicted_high": round(predicted_high, 2),
            "change_amount": round(change, 2),
            "change_pct": round(change_pct, 2),
            "direction": direction,
            "advice": advice,
            "forecast_dates": forecast["ds"].dt.strftime(
                "%Y-%m-%d"
            ).tolist(),
            "forecast_prices": [
                round(p, 2) for p in forecast["yhat"].tolist()
            ],
        }