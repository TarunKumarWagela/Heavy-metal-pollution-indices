"""Standards blueprint."""

from flask import Blueprint, jsonify, render_template
from app.models import WaterStandard
from src.standards.standards_loader import get_all_profiles, get_standards_table

standards_bp = Blueprint("standards", __name__)


@standards_bp.get("/standards")
def list_standards():
    standards = WaterStandard.query.all()
    return jsonify([
        {
            "id": s.id,
            "standard_name": s.standard_name,
            "version": s.version,
            "metal": s.metal,
            "parameter": s.parameter,
            "chemical_species": s.chemical_species,
            "acceptable_limit": s.acceptable_limit,
            "permissible_limit": s.permissible_limit,
            "guideline_value": s.guideline_value,
            "unit": s.unit,
            "notes": s.notes,
        }
        for s in standards
    ])


@standards_bp.get("/standards/profiles")
def list_profiles():
    return jsonify(get_all_profiles())


@standards_bp.get("/standards/profile/<profile_name>")
def get_profile(profile_name: str):
    return jsonify(get_standards_table(profile_name))


@standards_bp.get("/standards-page")
def standards_page():
    return render_template("standards.html")
