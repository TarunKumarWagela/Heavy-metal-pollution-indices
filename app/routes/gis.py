"""GIS blueprint — map data endpoints."""

from flask import Blueprint, jsonify, request
from app.models import Sample, db
from sqlalchemy import func

gis_bp = Blueprint("gis", __name__)


VALID_GIS_METALS = {"Fe", "As", "U", "Mn", "Cu", "Pb", "Zn", "Ni", "Cd", "Cr"}


@gis_bp.get("/samples")
def get_map_samples():
    """Return all samples with valid coordinates for mapping."""
    state = request.args.get("state")
    metal = request.args.get("metal")

    if metal and metal not in VALID_GIS_METALS:
        metal = None

    query = Sample.query.filter(
        Sample.latitude.isnot(None),
        Sample.longitude.isnot(None),
    )
    if state:
        query = query.filter(Sample.state == state)

    samples = query.limit(2000).all()

    features = []
    for s in samples:
        metal_val = getattr(s, metal, None) if metal else None
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s.longitude, s.latitude],
            },
            "properties": {
                "id": s.id,
                "sample_id": s.sample_id,
                "state": s.state,
                "district": s.district,
                "station": s.station,
                "sample_date": s.sample_date.isoformat() if s.sample_date else None,
                "pH": s.pH,
                "TDS": s.TDS,
                "Fe": s.Fe, "As": s.As, "Mn": s.Mn, "Cu": s.Cu,
                "Pb": s.Pb, "Zn": s.Zn, "Ni": s.Ni, "Cd": s.Cd, "Cr": s.Cr,
                "selected_metal_value": metal_val,
                "selected_metal": metal,
            },
        })

    return jsonify({
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
    })


@gis_bp.get("/states")
def get_states():
    states = db.session.query(
        Sample.state, func.count(Sample.id).label("count")
    ).filter(Sample.state.isnot(None)).group_by(Sample.state).all()
    return jsonify([{"state": s.state, "count": s.count} for s in states])
