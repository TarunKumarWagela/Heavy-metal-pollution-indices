"""Dataset management blueprint."""

from __future__ import annotations

import io
from flask import (
    Blueprint, request, jsonify, current_app,
    render_template, send_file,
)
from app.models import DatasetUpload, Sample, db
from app.services.dataset_service import process_upload, SAMPLE_CSV_TEMPLATE

dataset_bp = Blueprint("dataset", __name__)


@dataset_bp.get("/")
def dataset_page():
    return render_template("dataset.html")


@dataset_bp.get("/sample-csv")
def download_sample_csv():
    """Provide a sample CSV template for download."""
    buf = io.BytesIO(SAMPLE_CSV_TEMPLATE.encode("utf-8"))
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name="hmpias_sample_template.csv",
    )


@dataset_bp.post("/upload")
def upload_dataset():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    allowed = current_app.config.get("ALLOWED_EXTENSIONS", {"csv", "xlsx", "xls"})
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        return jsonify({"error": f"File type '.{ext}' not allowed. Allowed formats: {sorted(list(allowed))}"}), 400

    column_mapping = {}
    if request.form.get("column_mapping"):
        import json
        try:
            column_mapping = json.loads(request.form["column_mapping"])
        except Exception:
            return jsonify({"error": "Invalid column_mapping JSON"}), 400

    notes = request.form.get("notes", "")

    try:
        result = process_upload(
            file_storage=file,
            column_mapping=column_mapping,
            upload_folder=current_app.config["UPLOAD_FOLDER"],
            notes=notes,
        )
        return jsonify(result), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dataset_bp.get("/uploads")
def list_uploads():
    uploads = DatasetUpload.query.order_by(DatasetUpload.uploaded_at.desc()).limit(50).all()
    return jsonify([
        {
            "id": u.id,
            "filename": u.original_filename,
            "row_count": u.row_count,
            "status": u.processing_status,
            "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
            "validation_summary": u.validation_summary,
        }
        for u in uploads
    ])


@dataset_bp.get("/uploads/<int:upload_id>/samples")
def list_samples(upload_id: int):
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    samples = Sample.query.filter_by(upload_id=upload_id).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "upload_id": upload_id,
        "total": samples.total,
        "page": page,
        "per_page": per_page,
        "samples": [s.to_dict() for s in samples.items],
    })


@dataset_bp.delete("/uploads/<int:upload_id>")
def delete_upload(upload_id: int):
    upload = db.get_or_404(DatasetUpload, upload_id)
    db.session.delete(upload)
    db.session.commit()
    return jsonify({"message": f"Upload {upload_id} and all samples deleted."})


@dataset_bp.get("/validate")
def validate_page():
    return render_template("dataset.html")


@dataset_bp.post("/api/validate")
def validate_uploaded():
    """Re-validate an already uploaded file."""
    from src.validation.validator import validate_dataframe
    upload_id = request.json.get("upload_id") if request.is_json else None
    if not upload_id:
        return jsonify({"error": "upload_id required"}), 400

    upload = db.get_or_404(DatasetUpload, upload_id)
    from app.services.dataset_service import read_uploaded_file
    try:
        # Enforce that file_path resides within configured UPLOAD_FOLDER
        upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
        target_path = Path(upload.file_path).resolve()
        if not target_path.is_relative_to(upload_folder):
            return jsonify({"error": "Invalid file location"}), 403

        df = read_uploaded_file(str(target_path))
        vr = validate_dataframe(df)
        return jsonify({
            "upload_id": upload_id,
            "validation_summary": vr.summary,
            "warnings": [
                {"field": w.field, "issue": w.issue, "severity": w.severity}
                for w in vr.warnings[:100]
            ],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
