"""Soil/Sediment indices blueprint — separate namespace from groundwater."""

from flask import Blueprint, jsonify, request
from src.indices.soil_indices import (
    calculate_contamination_factor, calculate_pli, calculate_igeo,
    pli_result_to_dict, igeo_result_to_dict,
)

soil_bp = Blueprint("soil", __name__)

_DOMAIN_NOTE = (
    "These soil/sediment indices apply exclusively to mg/kg dry-weight measurements. "
    "They must NOT be applied to drinking-water samples. "
    "Background values are geochemical reference values, not drinking-water limits."
)


@soil_bp.post("/calculate/cf")
def calculate_cf():
    """
    Calculate Contamination Factor for a single metal.
    Body: {"metal": "Pb", "measured": 45.2, "background": 20.0}
    """
    data = request.get_json(silent=True) or {}
    metal = data.get("metal", "unknown")
    measured = data.get("measured")
    background = data.get("background")

    if measured is None or background is None:
        return jsonify({"error": "measured and background required"}), 400

    try:
        result = calculate_contamination_factor(float(measured), float(background), metal)
        return jsonify({
            "domain": "soil_sediment",
            "domain_note": _DOMAIN_NOTE,
            "metal": result.metal,
            "measured_mg_kg_dw": result.measured_concentration,
            "background_mg_kg_dw": result.background_value,
            "contamination_factor_CF": round(result.cf_value, 6),
            "classification": result.classification,
            "citation": "Tomlinson et al. (1980). Helgoländer Meeresuntersuchungen, 33(1–4), 566–575.",
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@soil_bp.post("/calculate/pli")
def calculate_pli_endpoint():
    """
    Calculate PLI for multiple metals.
    Body: {
      "measurements": {"Pb": 45.2, "Cd": 2.1, "Cr": 90.0},
      "background_values": {"Pb": 20.0, "Cd": 0.35, "Cr": 70.0}
    }
    """
    data = request.get_json(silent=True) or {}
    measurements = data.get("measurements", {})
    background = data.get("background_values", {})

    if not measurements or not background:
        return jsonify({"error": "measurements and background_values required"}), 400

    try:
        result = calculate_pli(measurements, background)
        d = pli_result_to_dict(result)
        d["domain"] = "soil_sediment"
        d["domain_note"] = _DOMAIN_NOTE
        d["citation"] = "Tomlinson et al. (1980). Helgoländer Meeresuntersuchungen, 33(1–4), 566–575."
        return jsonify(d)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@soil_bp.post("/calculate/igeo")
def calculate_igeo_endpoint():
    """
    Calculate Geo-accumulation Index for a single metal.
    Body: {"metal": "Pb", "measured": 45.2, "background": 20.0}
    """
    data = request.get_json(silent=True) or {}
    metal = data.get("metal", "unknown")
    measured = data.get("measured")
    background = data.get("background")

    if measured is None or background is None:
        return jsonify({"error": "measured and background required"}), 400

    try:
        result = calculate_igeo(float(measured), float(background), metal)
        d = igeo_result_to_dict(result)
        d["domain"] = "soil_sediment"
        d["domain_note"] = _DOMAIN_NOTE
        d["citation"] = "Müller, G. (1969). GeoJournal, 2(3), 108–118."
        return jsonify(d)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
