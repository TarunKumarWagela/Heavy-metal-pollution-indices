"""Calculations blueprint — HPI, HEI, Degree of Contamination."""

from __future__ import annotations

from flask import Blueprint, request, jsonify, render_template
from app.models import db
from app.services.calculation_service import (
    calculate_indices_for_sample,
    calculate_for_dataset,
)
from src.indices.hpi import calculate_hpi, hpi_result_to_dict
from src.indices.hei import calculate_hei, hei_result_to_dict
from src.indices.degree_of_contamination import (
    calculate_degree_of_contamination, cd_result_to_dict,
)

calc_bp = Blueprint("calculations", __name__)


@calc_bp.get("/calculator")
def calculator_page():
    return render_template("calculator.html")


def _get_json_body():
    if not request.is_json:
        return None, jsonify({"error": "Content-Type must be application/json"}), 400
    data = request.get_json(silent=True)
    if data is None:
        return None, jsonify({"error": "Invalid JSON body"}), 400
    return data, None, None


# ------------------------------------------------------------------ #
# Quick calculation endpoints (without DB persistence)
# ------------------------------------------------------------------ #

@calc_bp.post("/calculate/hpi")
def calculate_hpi_endpoint():
    """
    Calculate HPI from raw measurements provided in request body.

    Body:
    {
      "measurements": {"Pb": 0.015, "Cd": 0.002, "Cr": 0.030},
      "standards":    {"Pb": 0.010, "Cd": 0.003, "Cr": 0.050},
      "ideal_values": {"Pb": 0.0, "Cd": 0.0, "Cr": 0.0},
      "bdl_flags":    {"Pb": false},
      "classification_profile": "mohan"
    }
    """
    data, err, code = _get_json_body()
    if err:
        return err, code

    measurements = data.get("measurements", {})
    standards = data.get("standards", {})
    ideal_values = data.get("ideal_values")
    bdl_flags = data.get("bdl_flags")
    profile = data.get("classification_profile", "mohan")

    if not measurements:
        return jsonify({"error": "measurements required"}), 400
    if not standards:
        return jsonify({"error": "standards required"}), 400

    try:
        result = calculate_hpi(measurements, standards, ideal_values, bdl_flags, profile)
        return jsonify(hpi_result_to_dict(result))
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@calc_bp.post("/calculate/hei")
def calculate_hei_endpoint():
    data, err, code = _get_json_body()
    if err:
        return err, code

    measurements = data.get("measurements", {})
    standards = data.get("standards", {})
    bdl_flags = data.get("bdl_flags")

    if not measurements or not standards:
        return jsonify({"error": "measurements and standards required"}), 400

    try:
        result = calculate_hei(measurements, standards, bdl_flags)
        return jsonify(hei_result_to_dict(result))
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@calc_bp.post("/calculate/cd")
def calculate_cd_endpoint():
    data, err, code = _get_json_body()
    if err:
        return err, code

    measurements = data.get("measurements", {})
    references = data.get("reference_values") or data.get("standards", {})
    bdl_flags = data.get("bdl_flags")
    non_negative = data.get("non_negative", False)

    if not measurements or not references:
        return jsonify({"error": "measurements and reference_values required"}), 400

    try:
        result = calculate_degree_of_contamination(
            measurements, references, bdl_flags, non_negative
        )
        return jsonify(cd_result_to_dict(result))
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@calc_bp.post("/calculate/all")
def calculate_all_endpoint():
    """Calculate HPI, HEI, and Cd_index in one request."""
    data, err, code = _get_json_body()
    if err:
        return err, code

    measurements = data.get("measurements", {})
    standards = data.get("standards", {})
    bdl_flags = data.get("bdl_flags")
    non_negative = data.get("non_negative", False)
    profile = data.get("classification_profile", "mohan")

    if not measurements or not standards:
        return jsonify({"error": "measurements and standards required"}), 400

    results = {}

    try:
        hpi = calculate_hpi(measurements, standards, bdl_flags=bdl_flags,
                            classification_profile=profile)
        results["HPI"] = hpi_result_to_dict(hpi)
    except ValueError as e:
        results["HPI"] = {"error": str(e)}

    try:
        hei = calculate_hei(measurements, standards, bdl_flags)
        results["HEI"] = hei_result_to_dict(hei)
    except ValueError as e:
        results["HEI"] = {"error": str(e)}

    try:
        cd = calculate_degree_of_contamination(
            measurements, standards, bdl_flags, non_negative
        )
        results["Cd_index"] = cd_result_to_dict(cd)
    except ValueError as e:
        results["Cd_index"] = {"error": str(e)}

    return jsonify(results)


# ------------------------------------------------------------------ #
# DB-backed calculation for uploaded samples
# ------------------------------------------------------------------ #

@calc_bp.post("/calculate/sample/<int:sample_id>")
def calculate_for_sample(sample_id: int):
    data = request.get_json(silent=True) or {}
    standard_profile = data.get("standard_profile", "BIS IS 10500")
    index_types = data.get("index_types", ["HPI", "HEI", "Cd_index"])
    non_negative = data.get("non_negative_cd", False)

    try:
        result = calculate_indices_for_sample(
            sample_id=sample_id,
            standard_profile=standard_profile,
            index_types=index_types,
            non_negative_cd=non_negative,
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@calc_bp.post("/calculate/dataset/<int:upload_id>")
def calculate_for_upload(upload_id: int):
    data = request.get_json(silent=True) or {}
    standard_profile = data.get("standard_profile", "BIS IS 10500")
    index_types = data.get("index_types", ["HPI", "HEI", "Cd_index"])

    try:
        result = calculate_for_dataset(upload_id, standard_profile, index_types)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@calc_bp.get("/results/<int:result_id>")
def get_result(result_id: int):
    from app.models import IndexResult, MetalContribution
    ir = db.get_or_404(IndexResult, result_id)
    contributions = MetalContribution.query.filter_by(index_result_id=ir.id).all()

    return jsonify({
        "id": ir.id,
        "sample_id": ir.sample_id,
        "standard_profile": ir.standard_profile,
        "index_type": ir.index_type,
        "index_value": ir.index_value,
        "classification": ir.classification,
        "metals_included": ir.metals_included,
        "metals_excluded": ir.metals_excluded,
        "calculated_at": ir.calculated_at.isoformat() if ir.calculated_at else None,
        "contributions": [
            {
                "metal": c.metal,
                "measured": c.measured_concentration,
                "limit": c.reference_limit,
                "weight": c.weight,
                "sub_index": c.sub_index,
                "effective_contribution": c.effective_contribution,
                "percentage_contribution": c.percentage_contribution,
            }
            for c in contributions
        ],
    })
