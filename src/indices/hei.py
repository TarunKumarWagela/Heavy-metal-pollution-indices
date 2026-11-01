"""
Heavy Metal Evaluation Index (HEI) Calculator
==============================================

Scientific basis
----------------
Edet, A.E., & Offiong, O.E. (2002). Evaluation of water quality pollution
indices for heavy metal contamination monitoring. A study case from Akpabuyo-
Odukpani area, Lower Cross River Basin (southeastern Nigeria).
GeoJournal, 57(4), 295–304.
https://doi.org/10.1023/B:GEJO.0000007250.92458.de

Formula
-------
    HEI = Σ (Hc_i / Hmac_i)

Where:
    Hc_i   = measured concentration of metal i (mg/L)
    Hmac_i = maximum acceptable concentration (permissible/guideline limit) (mg/L)

Classification (Edet & Offiong 2002; literature-based)
    HEI < 10   → Low
    10 ≤ HEI < 20  → Medium
    HEI ≥ 20   → High

NOTE: Classification thresholds are from the original publication and are
adopted widely in Indian groundwater literature. They are not universal
regulatory classifications.

BDL handling
------------
BDL metals are excluded with a warning; NOT set to zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ============================================================ #
#  Data classes                                                 #
# ============================================================ #

@dataclass
class MetalHEIResult:
    """Per-metal HEI components."""
    metal: str
    measured_concentration: float   # Hc_i (mg/L)
    max_acceptable_conc: float      # Hmac_i (mg/L)
    ratio: float                    # Hc_i / Hmac_i


@dataclass
class HEIResult:
    """Complete HEI calculation result for one sample."""
    hei: float
    classification: str
    classification_source: str
    metals_used: list[str]
    metals_excluded: dict[str, str]
    per_metal: list[MetalHEIResult]
    warnings: list[str] = field(default_factory=list)
    methodology_note: str = (
        "HEI calculated per Edet & Offiong (2002). "
        "HEI = Σ(Hc_i/Hmac_i). "
        "Hmac_i is the permissible/guideline limit for each metal."
    )


# ============================================================ #
#  Classification                                               #
# ============================================================ #

_EDET_CLASSIFICATION = {
    "source": "Edet & Offiong (2002) — literature-based classification",
    "note": "Not a universal regulatory threshold.",
    "thresholds": [
        (10,  "Low"),
        (20,  "Medium"),
    ],
    "above_last": "High",
}


def _classify_hei(hei: float) -> tuple[str, str]:
    cfg = _EDET_CLASSIFICATION
    for threshold, label in cfg["thresholds"]:
        if hei < threshold:
            return label, cfg["source"]
    return cfg["above_last"], cfg["source"]


# ============================================================ #
#  Core calculation function                                    #
# ============================================================ #

def calculate_hei(
    measurements: dict[str, float],
    standards: dict[str, float],
    bdl_flags: dict[str, bool] | None = None,
) -> HEIResult:
    """
    Compute the Heavy Metal Evaluation Index for a single sample.

    Parameters
    ----------
    measurements : dict[str, float]
        Metal symbol → measured concentration in mg/L.

    standards : dict[str, float]
        Metal symbol → maximum acceptable concentration in mg/L.
        Must be > 0.

    bdl_flags : dict[str, bool] | None
        Metal symbol → True if BDL. BDL metals excluded.

    Returns
    -------
    HEIResult
    """
    if bdl_flags is None:
        bdl_flags = {}

    warnings: list[str] = []
    excluded: dict[str, str] = {}
    per_metal_results: list[MetalHEIResult] = []

    common_metals = set(measurements.keys()) & set(standards.keys())

    for metal in sorted(common_metals):
        Hc = measurements[metal]
        Hmac = standards[metal]

        if bdl_flags.get(metal, False):
            excluded[metal] = "BDL — excluded from HEI"
            warnings.append(f"{metal}: BDL flag — excluded.")
            continue

        if Hc is None or (isinstance(Hc, float) and math.isnan(Hc)):
            excluded[metal] = "Missing measurement"
            warnings.append(f"{metal}: Missing — excluded.")
            continue

        if Hc < 0:
            excluded[metal] = f"Negative concentration ({Hc} mg/L)"
            warnings.append(f"{metal}: Negative value — excluded.")
            continue

        if Hmac is None or Hmac <= 0:
            excluded[metal] = f"Invalid Hmac ({Hmac}) — must be > 0"
            warnings.append(f"{metal}: Invalid standard — excluded.")
            continue

        ratio = Hc / Hmac
        per_metal_results.append(
            MetalHEIResult(metal=metal, measured_concentration=Hc,
                           max_acceptable_conc=Hmac, ratio=ratio)
        )

    if not per_metal_results:
        raise ValueError(
            "No valid metals for HEI calculation. "
            f"Excluded: {excluded}. Warnings: {warnings}"
        )

    hei = sum(r.ratio for r in per_metal_results)
    classification, class_source = _classify_hei(hei)

    return HEIResult(
        hei=hei,
        classification=classification,
        classification_source=class_source,
        metals_used=[r.metal for r in per_metal_results],
        metals_excluded=excluded,
        per_metal=per_metal_results,
        warnings=warnings,
    )


def hei_result_to_dict(result: HEIResult) -> dict[str, Any]:
    return {
        "hei": round(result.hei, 6),
        "classification": result.classification,
        "classification_source": result.classification_source,
        "metals_used": result.metals_used,
        "metals_excluded": result.metals_excluded,
        "warnings": result.warnings,
        "methodology_note": result.methodology_note,
        "per_metal": [
            {
                "metal": r.metal,
                "measured_concentration_mg_L": round(r.measured_concentration, 6),
                "max_acceptable_conc_mg_L": round(r.max_acceptable_conc, 6),
                "ratio_Hc_Hmac": round(r.ratio, 6),
            }
            for r in result.per_metal
        ],
    }
