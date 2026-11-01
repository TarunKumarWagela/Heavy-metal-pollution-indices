"""Reports blueprint — PDF, Excel, CSV downloads."""

from __future__ import annotations
import io
from flask import Blueprint, jsonify, request, send_file
from app.models import Sample, IndexResult, DatasetUpload

reports_bp = Blueprint("reports", __name__)


@reports_bp.get("/export/csv/<int:upload_id>")
def export_csv(upload_id: int):
    samples = Sample.query.filter_by(upload_id=upload_id).all()
    if not samples:
        return jsonify({"error": "No samples found"}), 404
    from app.services.report_service import generate_csv
    data = [s.to_dict() for s in samples]
    csv_bytes = generate_csv(data)
    buf = io.BytesIO(csv_bytes)
    return send_file(buf, mimetype="text/csv", as_attachment=True,
                     download_name=f"hmpias_upload_{upload_id}.csv")


@reports_bp.get("/export/excel/<int:upload_id>")
def export_excel(upload_id: int):
    samples = Sample.query.filter_by(upload_id=upload_id).all()
    if not samples:
        return jsonify({"error": "No samples found"}), 404

    sample_ids = [s.id for s in samples]
    index_results = IndexResult.query.filter(
        IndexResult.sample_id.in_(sample_ids)
    ).all()

    from app.services.report_service import generate_excel
    sample_dicts = [s.to_dict() for s in samples]
    idx_dicts = [
        {
            "sample_id": r.sample_id,
            "index_type": r.index_type,
            "index_value": r.index_value,
            "classification": r.classification,
            "standard_profile": r.standard_profile,
            "metals_included": r.metals_included,
        }
        for r in index_results
    ]
    excel_bytes = generate_excel(sample_dicts, idx_dicts)
    buf = io.BytesIO(excel_bytes)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"hmpias_upload_{upload_id}.xlsx",
    )


@reports_bp.get("/export/pdf/<int:sample_id>")
def export_pdf(sample_id: int):
    sample = Sample.query.get_or_404(sample_id)
    index_results = IndexResult.query.filter_by(sample_id=sample_id).all()

    indices: dict = {"indices": {}}
    for ir in index_results:
        from app.models import MetalContribution
        contributions = MetalContribution.query.filter_by(index_result_id=ir.id).all()
        indices["indices"][ir.index_type] = {
            {"HPI": "hpi", "HEI": "hei", "Cd_index": "cd_index"}.get(ir.index_type, "value"):
                ir.index_value,
            "classification": ir.classification,
            "per_metal": [
                {
                    "metal": c.metal,
                    "measured_concentration_mg_L": c.measured_concentration,
                    "reference_limit_mg_L": c.reference_limit,
                    "sub_index_Qi": c.sub_index,
                    "effective_contribution": c.effective_contribution,
                    "percentage_contribution": c.percentage_contribution,
                }
                for c in contributions
            ],
        }

    standard_profile = index_results[0].standard_profile if index_results else "N/A"

    from app.services.report_service import generate_pdf_report
    pdf_bytes = generate_pdf_report(sample.to_dict(), indices, standard_profile)
    buf = io.BytesIO(pdf_bytes)
    return send_file(
        buf, mimetype="application/pdf",
        as_attachment=True,
        download_name=f"hmpias_sample_{sample_id}_report.pdf",
    )


@reports_bp.get("/reports")
def reports_page():
    from flask import render_template
    return render_template("reports.html")
