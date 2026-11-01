"""
Degree of Contamination (Cd_index) Calculator
==============================================

Scientific basis
----------------
Backman, B., Bodiš, D., Lahermo, P., Rapant, S., & Tarvainen, T. (1998).
Application of a groundwater contamination index in Finland and Slovakia.
Environmental Geology, 36(1–2), 55–64.
https://doi.org/10.1007/s002540050320

NOTE ON NOTATION: In this module, the word "Cd" by itself always refers to
the index "Degree of Contamination", never to the element cadmium.
The element cadmium is referenced only as 'cadmium' or with explicit context.

Formula
-------
    CF_i       = (C_A_i / C_N_i) - 1
    Cd_index   = Σ CF_i

Where:
    C_A_i = analysed (measured) concentration of component i
    C_N_i = background / reference value for component i
             (In drinking-water context: the permissible/guideline limit)
    CF_i  = contamination factor for component i

Signed Cd_index
---------------
The Backman formulation preserves sign. CF_i < 0 when C_A_i < C_N_i,
meaning the sample is cleaner than background for that component.
The aggregate Cd_index can therefore be negative.

Non-negative variant
--------------------
Some authors use max(CF_i, 0) to consider only enrichment.
This variant is optionally available via `non_negative=True` but is
clearly labelled as a departure from the original Backman formulation.

Classification (Backman et al. 1998 — literature-based)
    Cd_index < 0          → Very low / negative (cleaner than background)
    0 ≤ Cd_index < 1      → Low
    1 ≤ Cd_index < 3      → Medium
    3 ≤ Cd_index < 6      → High
    Cd_index ≥ 6          → Very High

Classification is literature-based and not a regulatory threshold.

BDL handling
------------
BDL measurements are excluded; NOT silently set to zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ============================================================ #
#  Data classes                                                 #
# ============================================================ #

@dataclass
class MetalCFResult:
    """Per-metal contamination factor (CF_i)."""
    metal: str
    measured_concentration: float   # C_A_i (mg/L)
    reference_value: float          # C_N_i (mg/L)
    contamination_factor: float     # CF_i = (C_A_i / C_N_i) - 1
    is_enriched: bool               # CF_i > 0


@dataclass
class DegreeOfContaminationResult:
    """Complete Degree of Contamination result for one sample."""
    cd_index: float                   # Σ CF_i  ("Cd" = index name, not cadmium element)
    classification: str
    classification_source: str
    variant: str                      # "backman_signed" or "non_negative"
    metals_used: list[str]
    metals_excluded: dict[str, str]
    per_metal: list[MetalCFResult]
    warnings: list[str] = field(default_factory=list)
    methodology_note: str = (
        "Degree of Contamination (Cd_index) calculated per Backman et al. (1998). "
        "CF_i = (C_A_i/C_N_i) - 1; Cd_index = Σ CF_i. "
        "Signed Backman formulation preserves negative values. "
        "IMPORTANT: 'Cd' here refers to the contamination index, "
        "NOT to the element cadmium (element symbol: Cd)."
    )


# ============================================================ #
#  Classification                                               #
# ============================================================ #

_BACKMAN_CLASSIFICATION = [
    # (upper_bound_exclusive, label)
    (0,  "Very Low (below background)"),
    (1,  "Low"),
    (3,  "Medium"),
    (6,  "High"),
]
_BACKMAN_SOURCE = "Backman et al. (1998) — literature-based"
_BACKMAN_NOTE = "Not a universal regulatory threshold."


def _classify_cd_index(cd_index: float) -> tuple[str, str]:
    for upper, label in _BACKMAN_CLASSIFICATION:
        if cd_index < upper:
            return label, _BACKMAN_SOURCE
    return "Very High", _BACKMAN_SOURCE


# ============================================================ #
#  Core calculation function                                    #
# ============================================================ #

def calculate_degree_of_contamination(
    measurements: dict[str, float],
    reference_values: dict[str, float],
    bdl_flags: dict[str, bool] | None = None,
    non_negative: bool = False,
) -> DegreeOfContaminationResult:
    """
    Compute the Degree of Contamination index (Cd_index) for a single sample.

    Parameters
    ----------
    measurements : dict[str, float]
        Metal symbol → measured concentration in mg/L.

    reference_values : dict[str, float]
        Metal symbol → reference / background value in mg/L.
        Must be > 0.

    bdl_flags : dict[str, bool] | None
        Metal symbol → True if BDL. BDL metals excluded.

    non_negative : bool
        If True, CF_i = max(CF_i, 0) is applied (non-Backman variant).
        Default: False (original Backman signed formulation).

    Returns
    -------
    DegreeOfContaminationResult
    """
    if bdl_flags is None:
        bdl_flags = {}

    warnings: list[str] = []
    excluded: dict[str, str] = {}
    per_metal_results: list[MetalCFResult] = []
    variant = "non_negative" if non_negative else "backman_signed"

    if non_negative:
        warnings.append(
            "Non-negative variant applied: CF_i = max(CF_i, 0). "
            "This departs from the original Backman et al. (1998) signed formulation."
        )

    common_metals = set(measurements.keys()) & set(reference_values.keys())

    for metal in sorted(common_metals):
        C_A = measurements[metal]
        C_N = reference_values[metal]

        if bdl_flags.get(metal, False):
            excluded[metal] = "BDL — excluded from Cd_index"
            warnings.append(f"{metal}: BDL — excluded.")
            continue

        if C_A is None or (isinstance(C_A, float) and math.isnan(C_A)):
            excluded[metal] = "Missing measurement"
            warnings.append(f"{metal}: Missing — excluded.")
            continue

        if C_A < 0:
            excluded[metal] = f"Negative concentration ({C_A} mg/L)"
            warnings.append(f"{metal}: Negative value — excluded.")
            continue

        if C_N is None or C_N <= 0:
            excluded[metal] = f"Invalid reference ({C_N}) — must be > 0"
            warnings.append(f"{metal}: Invalid reference — excluded.")
            continue

        CF_i = (C_A / C_N) - 1.0

        if non_negative:
            CF_i = max(CF_i, 0.0)

        per_metal_results.append(
            MetalCFResult(
                metal=metal,
                measured_concentration=C_A,
                reference_value=C_N,
                contamination_factor=CF_i,
                is_enriched=CF_i > 0,
            )
        )

    if not per_metal_results:
        raise ValueError(
            "No valid metals for Degree of Contamination calculation. "
            f"Excluded: {excluded}. Warnings: {warnings}"
        )

    cd_index = sum(r.contamination_factor for r in per_metal_results)
    classification, class_source = _classify_cd_index(cd_index)

    return DegreeOfContaminationResult(
        cd_index=cd_index,
        classification=classification,
        classification_source=class_source,
        variant=variant,
        metals_used=[r.metal for r in per_metal_results],
        metals_excluded=excluded,
        per_metal=per_metal_results,
        warnings=warnings,
    )


def cd_result_to_dict(result: DegreeOfContaminationResult) -> dict[str, Any]:
    return {
        "cd_index": round(result.cd_index, 6),
        "classification": result.classification,
        "classification_source": result.classification_source,
        "variant": result.variant,
        "metals_used": result.metals_used,
        "metals_excluded": result.metals_excluded,
        "warnings": result.warnings,
        "methodology_note": result.methodology_note,
        "per_metal": [
            {
                "metal": r.metal,
                "measured_concentration_mg_L": round(r.measured_concentration, 6),
                "reference_value_mg_L": round(r.reference_value, 6),
                "contamination_factor_CF": round(r.contamination_factor, 6),
                "is_enriched": r.is_enriched,
            }
            for r in result.per_metal
        ],
    }
