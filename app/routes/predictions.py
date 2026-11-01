"""Predictions blueprint — ML training and inference."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template, current_app
from app.models import Sample, MLModel, Prediction, db

pred_bp = Blueprint("predictions", __name__)


@pred_bp.get("/ml")
def ml_page():
    return render_template("prediction.html")


@pred_bp.post("/predict")
def predict():
    """
    Predict a metal concentration for given input features.

    Body:
    {
      "model_id": 1,
      "input_features": {"pH": 7.2, "EC": 850, "TDS": 520, ...},
      "sample_id": 5   // optional, to persist prediction
    }
    """
    data = request.get_json(silent=True) or {}
    model_id = data.get("model_id")
    input_features = data.get("input_features", {})
    sample_id = data.get("sample_id")

    if not model_id:
        return jsonify({"error": "model_id required"}), 400
    if not input_features:
        return jsonify({"error": "input_features required"}), 400

    ml_model = MLModel.query.get(model_id)
    if not ml_model or not ml_model.is_active:
        return jsonify({"error": f"Model {model_id} not found or inactive"}), 404

    try:
        from src.machine_learning.predict import predict_metal_concentration
        result = predict_metal_concentration(
            model_file_path=ml_model.file_path,
            input_features=input_features,
            target_metal=ml_model.target_variable,
        )

        # Persist if sample_id given
        if sample_id:
            pred = Prediction(
                sample_id=sample_id,
                ml_model_id=model_id,
                predicted_value=result["predicted_value_mg_L"],
                prediction_inputs=input_features,
                uncertainty_lower=result.get("uncertainty_lower_95ci"),
                uncertainty_upper=result.get("uncertainty_upper_95ci"),
            )
            db.session.add(pred)
            db.session.commit()
            result["prediction_db_id"] = pred.id

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@pred_bp.post("/ml/train")
def train_models():
    """Trigger model training on all uploaded samples."""
    data = request.get_json(silent=True) or {}
    upload_id = data.get("upload_id")
    model_type = data.get("model_type", "random_forest")

    import pandas as pd
    from app.models import Sample

    if upload_id:
        samples = Sample.query.filter_by(upload_id=upload_id).all()
    else:
        samples = Sample.query.all()

    if len(samples) < 30:
        return jsonify({
            "error": f"Insufficient data for training ({len(samples)} samples, min 30 required)."
        }), 422

    # Convert to DataFrame
    rows = [s.to_dict() for s in samples]
    df = pd.DataFrame(rows)

    model_folder = current_app.config["MODEL_FOLDER"]

    try:
        from src.machine_learning.train import train_all_metal_models
        results = train_all_metal_models(df, model_folder, model_type)
    except Exception as e:
        return jsonify({"error": f"Training failed: {e}"}), 500

    saved = []
    for r in results:
        existing = MLModel.query.filter_by(
            target_variable=r["target_variable"],
            model_type=r["model_type"],
            is_active=True,
        ).first()
        if existing:
            existing.is_active = False

        ml = MLModel(
            model_name=r["model_name"],
            target_variable=r["target_variable"],
            model_type=r["model_type"],
            task_type="regression",
            file_path=r["file_path"],
            feature_names=r["feature_names"],
            training_samples=r["training_samples"],
            mae=r["metrics"].get("mae"),
            rmse=r["metrics"].get("rmse"),
            r2=r["metrics"].get("r2"),
            training_dataset_description=(
                f"Trained on {r['training_samples']} samples from HMPIAS database. "
                f"Upload_id filter: {upload_id or 'all'}."
            ),
            limitations=(
                "Spatial generalization limited to training region. "
                "BDL samples excluded. Do not use for regulatory decisions."
            ),
            is_active=True,
        )
        db.session.add(ml)
        saved.append({
            "target": r["target_variable"],
            "model_type": r["model_type"],
            "metrics": r["metrics"],
        })

    db.session.commit()
    return jsonify({
        "message": f"Training complete. {len(saved)} models saved.",
        "models": saved,
    })


@pred_bp.get("/ml/models")
def list_models():
    models = MLModel.query.filter_by(is_active=True).all()
    return jsonify([
        {
            "id": m.id,
            "model_name": m.model_name,
            "target_variable": m.target_variable,
            "model_type": m.model_type,
            "training_samples": m.training_samples,
            "mae": m.mae,
            "rmse": m.rmse,
            "r2": m.r2,
            "feature_names": m.feature_names,
            "limitations": m.limitations,
            "trained_at": m.trained_at.isoformat() if m.trained_at else None,
        }
        for m in models
    ])
