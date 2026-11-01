"""
Soil/Sediment Indices: Contamination Factor, Pollution Load Index, Geo-accumulation Index
==========================================================================================

IMPORTANT DOMAIN SEPARATION
-----------------------------
These indices apply EXCLUSIVELY to soil and sediment samples measured in mg/kg dry weight.
They must NOT be applied to drinking-water samples.
Drinking-water quality is assessed using HPI, HEI, and Degree of Contamination (see other modules).

Scientific bases
----------------
1. Contamination Factor (CF) and Pollution Load Index (PLI):
   Tomlinson, D.L., Wilson, J.G., Harris, C.R., & Jeffrey, D.W. (1980).
   Problems in the assessment of heavy-metal levels in estuaries and the
   formation of a pollution index.
   Helgoländer Meeresuntersuchungen, 33(1–4), 566–575.
   https://doi.org/10.1007/BF02414780

2. Geo-accumulation Index (Igeo):
   Müller, G. (1969). Index of geo-accumulation in sediments of the Rhine River.
   GeoJournal, 2(3), 108–118.

Formulas
--------
    CF_i  = C_i / B_i
    PLI   = (CF_1 × CF_2 × … × CF_n) ^ (1/n)
    Igeo  = log2(C_n / (1.5 × B_n))

Where:
    C_i / C_n = measured metal concentration (mg/kg dry weight)
    B_i / B_n = geochemical background value (mg/kg dry weight)
    n         = number of metals

Classification — CF (Hakanson 1980):
    CF < 1     → Low
    1 ≤ CF < 3 → Moderate
    3 ≤ CF < 6 → Considerable
    CF ≥ 6     → Very High

Classification — PLI (Tomlinson et al. 1980):
    PLI < 1    → No pollution baseline
    PLI ≥ 1    → Progressive deterioration

Classification — Igeo (Müller 1969):
    Igeo ≤ 0        → Uncontaminated
    0 < Igeo ≤ 1    → Uncontaminated to Moderately Contaminated
    1 < Igeo ≤ 2    → Moderately Contaminated
    2 < Igeo ≤ 3    → Moderately to Heavily Contaminated
    3 < Igeo ≤ 4    → Heavily Contaminated
    4 < Igeo ≤ 5    → Heavily to Extremely Contaminated
    Igeo > 5        → Extremely Contaminated

All classifications are literature-based, not universal regulatory thresholds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ============================================================ #
#  Contamination Factor (CF)                                   #
# ============================================================ #

@dataclass
class CFResult:
    metal: str
    measured_concentration: float   # mg/kg dw
    background_value: float         # mg/kg dw
    cf_value: float                 # CF = C_i / B_i
    classification: str


def calculate_contamination_factor(
    measured: float,
    background: float,
    metal: str = "unknown",
) -> CFResult:
    """Compute CF for a single metal in a soil/sediment sample."""
    if background <= 0:
        raise ValueError(f"Background value for {metal} must be > 0, got {background}")
    if measured < 0:
        raise ValueError(f"Measured concentration for {metal} cannot be negative: {measured}")

    cf = measured / background
    classification = _classify_cf(cf)
    return CFResult(
        metal=metal,
        measured_concentration=measured,
        background_value=background,
        cf_value=cf,
        classification=classification,
    )


def _classify_cf(cf: float) -> str:
    if cf < 1:
        return "Low (CF < 1)"
    elif cf < 3:
        return "Moderate (1 ≤ CF < 3)"
    elif cf < 6:
        return "Considerable (3 ≤ CF < 6)"
    else:
        return "Very High (CF ≥ 6)"


# ============================================================ #
#  Pollution Load Index (PLI)                                  #
# ============================================================ #

@dataclass
class PLIResult:
    pli: float
    classification: str
    classification_source: str
    n_metals: int
    metals_used: list[str]
    metals_excluded: dict[str, str]
    per_metal_cf: list[CFResult]
    warnings: list[str] = field(default_factory=list)
    methodology_note: str = (
        "PLI calculated per Tomlinson et al. (1980). "
        "PLI = (CF_1 × … × CF_n)^(1/n). "
        "Applies to soil/sediment (mg/kg dry weight) only."
    )


def calculate_pli(
    measurements: dict[str, float],
    background_values: dict[str, float],
) -> PLIResult:
    """
    Compute the Pollution Load Index for a soil/sediment sample.

    Parameters
    ----------
    measurements : dict[str, float]
        Metal symbol → mg/kg dry weight.
    background_values : dict[str, float]
        Metal symbol → geochemical background mg/kg dry weight.

    Returns
    -------
    PLIResult
    """
    warnings: list[str] = []
    excluded: dict[str, str] = {}
    cf_results: list[CFResult] = []

    common = set(measurements.keys()) & set(background_values.keys())

    for metal in sorted(common):
        C = measurements[metal]
        B = background_values[metal]

        if C is None or (isinstance(C, float) and math.isnan(C)):
            excluded[metal] = "Missing measurement"
            continue
        if C < 0:
            excluded[metal] = f"Negative ({C} mg/kg)"
            warnings.append(f"{metal}: Negative — excluded.")
            continue
        if B is None or B <= 0:
            excluded[metal] = f"Invalid background ({B})"
            warnings.append(f"{metal}: Invalid background — excluded.")
            continue

        cf_results.append(calculate_contamination_factor(C, B, metal))

    if not cf_results:
        raise ValueError("No valid metals for PLI calculation.")

    n = len(cf_results)
    product = math.prod(r.cf_value for r in cf_results)
    pli = product ** (1.0 / n)

    classification = "No Pollution Baseline (PLI < 1)" if pli < 1 else "Progressive Deterioration (PLI ≥ 1)"
    source = "Tomlinson et al. (1980) — literature-based"

    return PLIResult(
        pli=pli,
        classification=classification,
        classification_source=source,
        n_metals=n,
        metals_used=[r.metal for r in cf_results],
        metals_excluded=excluded,
        per_metal_cf=cf_results,
        warnings=warnings,
    )


# ============================================================ #
#  Geo-accumulation Index (Igeo)                               #
# ============================================================ #

@dataclass
class IgeoResult:
    metal: str
    measured_concentration: float   # mg/kg dw
    background_value: float         # mg/kg dw
    igeo: float
    classification: str
    classification_source: str = "Müller (1969) — literature-based"
    methodology_note: str = (
        "Igeo = log2(C_n / (1.5 × B_n)). "
        "Applies to sediment/soil (mg/kg dry weight) only."
    )


def calculate_igeo(
    measured: float,
    background: float,
    metal: str = "unknown",
) -> IgeoResult:
    """Compute the Geo-accumulation Index for a single metal."""
    if background <= 0:
        raise ValueError(f"Background must be > 0 for {metal}, got {background}")
    if measured < 0:
        raise ValueError(f"Measured concentration cannot be negative for {metal}")

    denominator = 1.5 * background
    if denominator == 0:
        raise ValueError(f"1.5 × B = 0 for {metal} — cannot compute Igeo")

    ratio = measured / denominator
    if ratio <= 0:
        igeo = float("-inf")
    else:
        igeo = math.log2(ratio)

    return IgeoResult(
        metal=metal,
        measured_concentration=measured,
        background_value=background,
        igeo=igeo,
        classification=_classify_igeo(igeo),
    )


def _classify_igeo(igeo: float) -> str:
    if igeo <= 0:
        return "Class 0 — Uncontaminated"
    elif igeo <= 1:
        return "Class 1 — Uncontaminated to Moderately Contaminated"
    elif igeo <= 2:
        return "Class 2 — Moderately Contaminated"
    elif igeo <= 3:
        return "Class 3 — Moderately to Heavily Contaminated"
    elif igeo <= 4:
        return "Class 4 — Heavily Contaminated"
    elif igeo <= 5:
        return "Class 5 — Heavily to Extremely Contaminated"
    else:
        return "Class 6 — Extremely Contaminated"


def pli_result_to_dict(result: PLIResult) -> dict[str, Any]:
    return {
        "pli": round(result.pli, 6),
        "classification": result.classification,
        "classification_source": result.classification_source,
        "n_metals": result.n_metals,
        "metals_used": result.metals_used,
        "metals_excluded": result.metals_excluded,
        "warnings": result.warnings,
        "methodology_note": result.methodology_note,
        "per_metal_cf": [
            {
                "metal": r.metal,
                "measured_mg_kg_dw": round(r.measured_concentration, 6),
                "background_mg_kg_dw": round(r.background_value, 6),
                "cf": round(r.cf_value, 6),
                "classification": r.classification,
            }
            for r in result.per_metal_cf
        ],
    }


def igeo_result_to_dict(result: IgeoResult) -> dict[str, Any]:
    return {
        "metal": result.metal,
        "measured_mg_kg_dw": round(result.measured_concentration, 6),
        "background_mg_kg_dw": round(result.background_value, 6),
        "igeo": round(result.igeo, 6) if math.isfinite(result.igeo) else str(result.igeo),
        "classification": result.classification,
        "classification_source": result.classification_source,
        "methodology_note": result.methodology_note,
    }
