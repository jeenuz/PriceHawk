"""
Main script to train all ML models.
Run this after collecting enough price data.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from models.feature_engineer import PriceFeatureEngineer
from models.price_forecaster import PriceForecaster
from models.price_drop_classifier import PriceDropClassifier


def train_all_models():
    """Train Prophet + XGBoost on all available price data."""

    engineer = PriceFeatureEngineer()
    forecaster = PriceForecaster()
    classifier = PriceDropClassifier()

    try:
        logger.info("=" * 50)
        logger.info("PHASE 5: ML Model Training")
        logger.info("=" * 50)

        # Step 1 — Load all price history
        logger.info("Loading price history from PostgreSQL...")
        df = engineer.get_all_products_history(min_snapshots=2)

        if df.empty:
            logger.error(
                "No price data found! "
                "Run the pipeline first to collect data."
            )
            return

        logger.info(f"Total snapshots: {len(df)}")
        logger.info(f"Total products:  {df['product_id'].nunique()}")
        logger.info(f"Retailers:       {df['retailer'].unique()}")
        logger.info(
            f"Date range: {df['ds'].min()} to {df['ds'].max()}"
        )

        # Step 2 — Train Prophet forecasters
        logger.info("\n--- Training Prophet Models ---")
        prophet_models = forecaster.train_all_products(engineer)
        logger.info(
            f"Prophet: trained {len(prophet_models)} models"
        )

        # Step 3 — Engineer XGBoost features
        logger.info("\n--- Engineering XGBoost Features ---")
        feature_df = engineer.engineer_xgboost_features(df)
        logger.info(f"Features: {len(feature_df)} rows")

        if feature_df.empty:
            logger.warning(
                "Not enough data for XGBoost. "
                "Need at least 2 snapshots per product. "
                "Run pipeline again tomorrow!"
            )
        else:
            # Step 4 — Train XGBoost classifier
            logger.info("\n--- Training XGBoost Classifier ---")
            metrics = classifier.train(feature_df)

            if metrics:
                logger.info(
                    f"XGBoost accuracy: {metrics['accuracy']:.1%}"
                )
                logger.info("Feature importance:")
                for feat, imp in sorted(
                    metrics["feature_importance"].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    bar = "█" * int(imp * 50)
                    logger.info(f"  {feat:20s} {bar} {imp:.3f}")

        # Step 5 — Demo predictions
        logger.info("\n--- Sample Predictions ---")
        product_ids = df["product_id"].unique()[:3]

        for product_id in product_ids:
            result = forecaster.predict_product(
                product_id=int(product_id),
                engineer=engineer,
                periods=7
            )

            if "error" not in result:
                logger.info(f"\nProduct: {result['title'][:50]}")
                logger.info(
                    f"Current price:    ₹{result['current_price']:,.0f}"
                )
                logger.info(
                    f"Predicted 7 days: "
                    f"₹{result['predicted_price_7d']:,.0f}"
                )
                logger.info(
                    f"Change:           "
                    f"{result['change_pct']:+.1f}%"
                )
                logger.info(f"Direction:        {result['direction']}")
                logger.info(f"Advice:           {result['advice']}")
                logger.info(
                    f"Range:            "
                    f"₹{result['predicted_low']:,.0f} - "
                    f"₹{result['predicted_high']:,.0f}"
                )

        logger.info("\n" + "=" * 50)
        logger.info("ML Training Complete!")
        logger.info("=" * 50)

    finally:
        engineer.close()


if __name__ == "__main__":
    train_all_models()