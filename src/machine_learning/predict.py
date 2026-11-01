"""
Machine Learning — Prediction Module
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from src.machine_learning.train import load_model, _get_features_for_target

logger = logging.getLogger(__name__)


def predict_metal_concentration(
    model_file_path: str,
    input_features: dict[str, float],
    target_metal: str,
) -> dict[str, Any]:
    """
    Predict metal concentration using a saved model.

    Parameters
    ----------
    model_file_path : str
        Path to saved joblib model file.
    input_features : dict[str, float]
        Feature values (must not include the target metal).
    target_metal : str
        The metal being predicted (used for feature validation).

    Returns
    -------
    dict with predicted_value, model_type, metrics, warnings, uncertainty
    """
    # Safety: reject if target metal provided as input
    if target_metal in input_features:
        raise ValueError(
            f"Target metal '{target_metal}' must NOT be included in input features. "
            "This would cause data leakage."
        )

    model_data = load_model(model_file_path)
    model = model_data["model"]
    feature_names = model_data["feature_names"]
    metrics = model_data.get("metrics", {})
    model_type = model_data.get("model_type", "unknown")

    # Build feature vector
    X_row = []
    missing_features = []
    for feat in feature_names:
        val = input_features.get(feat)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            missing_features.append(feat)
            X_row.append(0.0)  # impute with 0 for missing; warn user
        else:
            X_row.append(float(val))

    X = np.array([X_row])
    predicted = float(model.predict(X)[0])

    # Uncertainty estimation for Random Forest (std of tree predictions)
    uncertainty_lower = None
    uncertainty_upper = None
    if hasattr(model, "estimators_"):
        tree_predictions = np.array([
            tree.predict(X)[0] for tree in model.estimators_
        ])
        std = float(tree_predictions.std())
        uncertainty_lower = max(0.0, predicted - 1.96 * std)
        uncertainty_upper = predicted + 1.96 * std

    warnings = []
    if missing_features:
        warnings.append(
            f"Missing features imputed with 0: {missing_features}. "
            "Prediction reliability may be reduced."
        )
    warnings.append(
        "Predictions are model estimates only. "
        "Do not use as sole basis for regulatory decisions. "
        "Validate with laboratory analysis."
    )

    return {
        "target_metal": target_metal,
        "predicted_value_mg_L": round(predicted, 6),
        "model_type": model_type,
        "model_metrics": metrics,
        "uncertainty_lower_95ci": round(uncertainty_lower, 6) if uncertainty_lower is not None else None,
        "uncertainty_upper_95ci": round(uncertainty_upper, 6) if uncertainty_upper is not None else None,
        "missing_features_imputed": missing_features,
        "limitations": (
            "Model trained on uploaded dataset only. "
            "Spatial generalization is limited. "
            "BDL samples were excluded from training. "
            "Do not extrapolate beyond training data distribution."
        ),
        "warnings": warnings,
    }
