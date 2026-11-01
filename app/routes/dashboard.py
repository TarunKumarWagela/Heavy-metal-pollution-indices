"""Dashboard blueprint — main landing page."""

from flask import Blueprint, render_template, jsonify
from app.models import Sample, DatasetUpload, IndexResult, db
from sqlalchemy import func

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    return render_template("dashboard.html")


@dashboard_bp.get("/api/dashboard/stats")
def dashboard_stats():
    total_samples = Sample.query.count()
    total_uploads = DatasetUpload.query.count()
    total_locations = db.session.query(
        func.count(func.distinct(Sample.station))
    ).scalar() or 0
    states = db.session.query(
        func.count(func.distinct(Sample.state))
    ).scalar() or 0

    # HPI results > 100 (critical threshold)
    critical_hpi = IndexResult.query.filter(
        IndexResult.index_type == "HPI",
        IndexResult.index_value >= 100,
    ).count()

    # Recent uploads
    recent = DatasetUpload.query.order_by(
        DatasetUpload.uploaded_at.desc()
    ).limit(5).all()

    # State-wise sample distribution
    state_counts = db.session.query(
        Sample.state, func.count(Sample.id).label("count")
    ).group_by(Sample.state).order_by(func.count(Sample.id).desc()).limit(15).all()

    # Metal-wise averages
    metals = ["Fe", "As", "Mn", "Cu", "Pb", "Zn", "Ni", "Cd", "Cr"]
    metal_stats = {}
    for metal in metals:
        col = getattr(Sample, metal)
        avg = db.session.query(func.avg(col)).scalar()
        metal_stats[metal] = round(float(avg), 6) if avg else None

    return jsonify({
        "total_samples": total_samples,
        "total_uploads": total_uploads,
        "total_locations": total_locations,
        "total_states": states,
        "critical_hpi_samples": critical_hpi,
        "recent_uploads": [
            {
                "id": u.id,
                "filename": u.original_filename,
                "rows": u.row_count,
                "status": u.processing_status,
                "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
            }
            for u in recent
        ],
        "state_distribution": [
            {"state": s.state or "Unknown", "count": s.count}
            for s in state_counts
        ],
        "metal_averages_mg_L": metal_stats,
    })
