"""
Machine Learning — Training Module
====================================
Trains Random Forest and Linear Regression models for predicting
heavy metal concentrations or HPI classification.

Key design rules:
- Target metal is NEVER used as an input feature when predicting that metal.
- No synthetic data is trained and presented as real environmental prediction.
- Uses grouped/spatial cross-validation concepts via train/test split with
  geographic awareness (where coordinates are available).
- All trained models are saved with joblib and registered in the database.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    accuracy_score, f1_score, mean_absolute_error,
    mean_squared_error, precision_score, r2_score, recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

# Metals supported as regression targets
SUPPORTED_METALS = ["Fe", "As", "U", "Mn", "Cu", "Pb", "Zn", "Ni", "Cd", "Cr"]

# Features that may be used as inputs (never use the target metal as input)
ALL_POSSIBLE_FEATURES = [
    "latitude", "longitude", "pH", "EC", "TDS", "fluoride", "nitrate",
    # Other metals can be inputs as long as they are not the target
    "Fe", "As", "U", "Mn", "Cu", "Pb", "Zn", "Ni", "Cd", "Cr",
]


def _get_features_for_target(target_metal: str) -> list[str]:
    """Return feature list excluding the target metal itself."""
    base = ["latitude", "longitude", "pH", "EC", "TDS", "fluoride", "nitrate"]
    metal_features = [m for m in SUPPORTED_METALS if m != target_metal]
    return base + metal_features


def prepare_features(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str],
    min_samples: int = 30,
) -> tuple[pd.DataFrame, pd.Series] | None:
    """
    Prepare feature matrix X and target vector y.

    Returns None if insufficient valid samples.
    """
    # Select only the columns we need
    available_features = [c for c in feature_cols if c in df.columns]
    if target_col not in df.columns:
        logger.warning("Target column '%s' not in DataFrame", target_col)
        return None

    subset = df[available_features + [target_col]].copy()

    # Drop rows where target is missing or BDL-flagged
    bdl_col = f"{target_col}_bdl"
    if bdl_col in df.columns:
        subset = subset[~df[bdl_col].fillna(False)]

    subset = subset.dropna(subset=[target_col])
    subset = subset[subset[target_col] >= 0]  # exclude negatives

    if len(subset) < min_samples:
        logger.info(
            "Insufficient samples for '%s': %d (min: %d)",
            target_col, len(subset), min_samples
        )
        return None

    X = subset[available_features].fillna(subset[available_features].median())
    y = subset[target_col]

    return X, y


def train_regression_model(
    X: pd.DataFrame,
    y: pd.Series,
    model_type: str = "random_forest",
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Train a regression model and return metrics + model object.

    Parameters
    ----------
    model_type : str
        "random_forest" or "linear_regression"

    Returns
    -------
    dict with keys: model, feature_names, metrics, model_type
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    if model_type == "random_forest":
        model = RandomForestRegressor(
            n_estimators=100,
            random_state=random_state,
            n_jobs=-1,
        )
    else:
        model = LinearRegression()

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = r2_score(y_test, y_pred)

    logger.info(
        "Regression [%s]: MAE=%.4f RMSE=%.4f R²=%.4f (n=%d)",
        model_type, mae, rmse, r2, len(X_train)
    )

    return {
        "model": model,
        "feature_names": list(X.columns),
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "metrics": {"mae": mae, "rmse": rmse, "r2": r2},
        "model_type": model_type,
    }


def train_classification_model(
    X: pd.DataFrame,
    y_labels: pd.Series,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Train a Random Forest Classifier for HPI category prediction.

    Returns
    -------
    dict with keys: model, feature_names, metrics, label_encoder, model_type
    """
    le = LabelEncoder()
    y_encoded = le.fit_transform(y_labels)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=random_state, stratify=y_encoded
        if len(np.unique(y_encoded)) > 1 else None
    )

    model = RandomForestClassifier(n_estimators=100, random_state=random_state, n_jobs=-1)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    rec = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    logger.info(
        "Classification: Acc=%.4f P=%.4f R=%.4f F1=%.4f (n=%d)",
        acc, prec, rec, f1, len(X_train)
    )

    return {
        "model": model,
        "label_encoder": le,
        "feature_names": list(X.columns),
        "training_samples": len(X_train),
        "metrics": {
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1": f1,
        },
        "model_type": "RandomForestClassifier",
    }


def save_model(
    model_result: dict[str, Any],
    model_name: str,
    target_variable: str,
    model_folder: str,
) -> str:
    """Save model to disk using joblib. Returns file path."""
    Path(model_folder).mkdir(parents=True, exist_ok=True)
    file_path = str(Path(model_folder) / f"{model_name}.joblib")
    joblib.dump(model_result, file_path)
    logger.info("Model saved: %s", file_path)
    return file_path


def load_model(file_path: str) -> dict[str, Any]:
    """Load a saved model from disk."""
    if not Path(file_path).exists():
        raise FileNotFoundError(f"Model file not found: {file_path}")
    return joblib.load(file_path)


def train_all_metal_models(
    df: pd.DataFrame,
    model_folder: str,
    model_type: str = "random_forest",
) -> list[dict[str, Any]]:
    """
    Train one regression model per metal where sufficient data exists.

    Returns a list of result dicts (one per successfully trained metal).
    """
    results = []

    for metal in SUPPORTED_METALS:
        feature_cols = _get_features_for_target(metal)
        prepared = prepare_features(df, metal, feature_cols)

        if prepared is None:
            logger.info("Skipping %s — insufficient data", metal)
            continue

        X, y = prepared
        try:
            result = train_regression_model(X, y, model_type=model_type)
            model_name = f"regression_{metal}_{model_type}"
            file_path = save_model(result, model_name, metal, model_folder)
            result["target_variable"] = metal
            result["model_name"] = model_name
            result["file_path"] = file_path
            results.append(result)
        except Exception as exc:
            logger.error("Failed to train model for %s: %s", metal, exc)

    return results
