import pandas as pd
import numpy as np
import joblib
import os
import shap
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)
from loguru import logger
from models.feature_engineer import PriceFeatureEngineer


class PriceDropClassifier:
    """
    XGBoost classifier that predicts whether a product's
    price will drop in the next 24 hours.

    Binary classification:
    1 = price will drop
    0 = price will stay same or rise
    """

    MODEL_PATH = "models/saved/xgboost_price_drop.joblib"
    EXPLAINER_PATH = "models/saved/shap_explainer.joblib"

    FEATURE_COLS = [
        "price_velocity",
        "vs_7d_avg",
        "vs_30d_avg",
        "days_since_drop",
        "price_range_pct",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
    ]

    def __init__(self):
        os.makedirs("models/saved", exist_ok=True)
        self.model = None
        self.explainer = None

    def train(
        self,
        feature_df: pd.DataFrame
    ) -> dict:
        """
        Train XGBoost classifier on engineered features.
        Returns training metrics.
        """
        if feature_df.empty:
            logger.error("No features to train on!")
            return {}

        logger.info(
            f"Training XGBoost on {len(feature_df)} samples..."
        )

        # Check class distribution
        drop_rate = feature_df["will_drop_24h"].mean()
        logger.info(
            f"Price drop rate in data: {drop_rate:.1%}"
        )

        X = feature_df[self.FEATURE_COLS]
        y = feature_df["will_drop_24h"]

        # Split data — keep time order for price data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=0.2,
            random_state=42,
            shuffle=True
        )

        logger.info(
            f"Train: {len(X_train)} samples, "
            f"Test: {len(X_test)} samples"
        )

        # Handle class imbalance
        # If drops are rare, weight them higher
        scale_pos_weight = (
            (y_train == 0).sum() / (y_train == 1).sum()
            if (y_train == 1).sum() > 0
            else 1
        )

        self.model = XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
        )

        # Train with early stopping
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        logger.info(f"XGBoost accuracy: {accuracy:.1%}")
        logger.info("\n" + classification_report(y_test, y_pred))

        # Build SHAP explainer
        logger.info("Building SHAP explainer...")
        self.explainer = shap.TreeExplainer(self.model)

        # Save models
        joblib.dump(self.model, self.MODEL_PATH)
        joblib.dump(self.explainer, self.EXPLAINER_PATH)
        logger.info("Models saved!")

        return {
            "accuracy": accuracy,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "drop_rate": drop_rate,
            "feature_importance": dict(zip(
                self.FEATURE_COLS,
                self.model.feature_importances_.tolist()
            ))
        }

    def load(self) -> bool:
        """Load saved model from disk."""
        if os.path.exists(self.MODEL_PATH):
            self.model = joblib.load(self.MODEL_PATH)
            if os.path.exists(self.EXPLAINER_PATH):
                self.explainer = joblib.load(self.EXPLAINER_PATH)
            logger.info("XGBoost model loaded!")
            return True
        return False

    def predict(
        self,
        features: dict
    ) -> dict:
        """
        Predict if price will drop for a single product.
        features = dict with same keys as FEATURE_COLS
        """
        if not self.model:
            if not self.load():
                return {"error": "No trained model found"}

        X = pd.DataFrame([features])[self.FEATURE_COLS]

        # Prediction
        prob = self.model.predict_proba(X)[0]
        will_drop = int(self.model.predict(X)[0])
        drop_probability = float(prob[1])

        # SHAP explanation
        explanation = self._explain(X)

        return {
            "will_drop": bool(will_drop),
            "drop_probability": round(drop_probability, 3),
            "confidence": self._confidence_label(drop_probability),
            "advice": (
                "Wait — price likely to drop soon!"
                if will_drop
                else "Safe to buy now"
            ),
            "explanation": explanation,
        }

    def _explain(self, X: pd.DataFrame) -> list[dict]:
        """Generate SHAP explanation for prediction."""
        if not self.explainer:
            return []

        shap_values = self.explainer.shap_values(X)

        # For binary classification, shap_values is array
        if isinstance(shap_values, list):
            values = shap_values[1][0]
        else:
            values = shap_values[0]

        # Build human-readable explanations
        explanations = []
        for feature, shap_val, feat_val in zip(
            self.FEATURE_COLS,
            values,
            X.values[0]
        ):
            if abs(shap_val) > 0.01:  # only significant features
                explanations.append({
                    "feature": feature,
                    "value": round(float(feat_val), 4),
                    "impact": round(float(shap_val), 4),
                    "direction": "increases" if shap_val > 0
                                else "decreases",
                    "human_readable": self._human_explain(
                        feature, feat_val, shap_val
                    ),
                })

        # Sort by impact magnitude
        explanations.sort(
            key=lambda x: abs(x["impact"]),
            reverse=True
        )
        return explanations[:5]  # top 5 reasons

    def _human_explain(
        self,
        feature: str,
        value: float,
        shap_val: float
    ) -> str:
        """Convert SHAP values to human readable text."""
        direction = "more likely" if shap_val > 0 else "less likely"

        explanations = {
            "price_velocity": (
                f"Price {'rising' if value > 0 else 'falling'} "
                f"recently → {direction} to drop"
            ),
            "vs_7d_avg": (
                f"Price {'above' if value > 0 else 'below'} "
                f"7-day average → {direction} to drop"
            ),
            "vs_30d_avg": (
                f"Price {'above' if value > 0 else 'below'} "
                f"30-day average → {direction} to drop"
            ),
            "days_since_drop": (
                f"Last drop was {int(value)} days ago "
                f"→ {direction} to drop"
            ),
            "price_range_pct": (
                f"Price varies {value:.1%} historically "
                f"→ {direction} to drop"
            ),
            "is_weekend": (
                f"{'Weekend' if value else 'Weekday'} "
                f"→ {direction} to drop"
            ),
            "day_of_week": (
                f"Day {int(value)} of week "
                f"→ {direction} to drop"
            ),
            "hour_of_day": (
                f"Hour {int(value)} of day "
                f"→ {direction} to drop"
            ),
        }
        return explanations.get(feature, f"{feature} → {direction}")

    def _confidence_label(self, probability: float) -> str:
        if probability >= 0.75:
            return "high"
        elif probability >= 0.55:
            return "medium"
        else:
            return "low"