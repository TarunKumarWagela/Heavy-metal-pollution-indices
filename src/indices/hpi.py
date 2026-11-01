"""
Heavy Metal Pollution Index (HPI) Calculator
=============================================

Scientific basis
----------------
Mohan, S.V., Nithila, P., & Reddy, S.J. (1996). Estimation of heavy metals
in drinking water and development of heavy metal pollution index.
Journal of Environmental Science and Health, Part A, 31(2), 283–289.
https://doi.org/10.1080/10934529609376357

Formula
-------
    Wi  = 1 / Si                              (weight of metal i)
    Qi  = |Mi - Ii| / |Si - Ii| × 100        (sub-index of metal i)
    HPI = Σ(Wi × Qi) / Σ(Wi)                 (aggregated index)

Where:
    Mi  = measured concentration (mg/L)
    Si  = permissible / reference limit (mg/L) — must be > 0
    Ii  = ideal (background / pristine) concentration
          Typically 0 for all heavy metals in drinking-water context.
          Mohan et al. use the WHO ideal values; we default to 0 for metals
          unless a non-zero ideal is explicitly supplied.

Contribution breakdown
----------------------
Effective contribution:
    EC_i  = (Wi × Qi) / Σ(Wi)          — sums to HPI

Percentage contribution:
    PC_i  = (Wi × Qi) / Σ(Wi × Qi) × 100   — sums to 100 %

Classification (Mohan et al. 1996; widely cited threshold)
    HPI < 100   →  Low / acceptable pollution
    HPI ≥ 100   →  High pollution / critical level

NOTE: The HPI = 100 threshold is the originally proposed critical level.
Many subsequent studies use finer classifications; these are not universally
adopted regulatory thresholds and are labelled as "literature-based" here.

BDL handling
------------
BDL samples are excluded from calculation with a warning.
They are NOT silently converted to zero.

Negative concentrations
-----------------------
Negative values are flagged and excluded with a warning.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# ============================================================ #
#  Data classes                                                 #
# ============================================================ #

@dataclass
class MetalHPIResult:
    """Per-metal HPI components."""
    metal: str
    measured_concentration: float     # Mi (mg/L)
    reference_limit: float            # Si (mg/L)
    ideal_value: float                # Ii (mg/L) — default 0
    weight: float                     # Wi = 1/Si
    sub_index: float                  # Qi
    weighted_numerator: float         # Wi × Qi
    effective_contribution: float     # (Wi×Qi)/Σ(Wi)
    percentage_contribution: float    # (Wi×Qi)/Σ(Wi×Qi) × 100


@dataclass
class HPIResult:
    """Complete HPI calculation result for one sample."""
    hpi: float
    classification: str
    classification_source: str
    metals_used: list[str]
    metals_excluded: dict[str, str]   # metal → reason for exclusion
    per_metal: list[MetalHPIResult]
    sum_weights: float                # Σ(Wi)
    sum_weighted_numerators: float    # Σ(Wi × Qi)
    warnings: list[str] = field(default_factory=list)
    methodology_note: str = (
        "HPI calculated per Mohan et al. (1996). "
        "Wi=1/Si; Qi=|Mi-Ii|/|Si-Ii|×100; HPI=ΣWiQi/ΣWi. "
        "Ideal values (Ii) set to 0 for all metals unless specified."
    )


# ============================================================ #
#  Classification profiles                                      #
# ============================================================ #

_MOHAN_CLASSIFICATION = {
    "source": "Mohan et al. (1996) — illustrative critical level",
    "note": (
        "This is a literature-based threshold, not a universal regulatory classification. "
        "HPI ≥ 100 indicates critical pollution levels per the original authors."
    ),
    "thresholds": [
        (100, "High Pollution (Critical)"),
    ],
    "below_first": "Low Pollution (Acceptable)",
}

# Extended literature classification used in many Indian groundwater studies
# Source: Prasad & Bose (2001) and subsequent authors; treat as literature-based.
_EXTENDED_CLASSIFICATION = {
    "source": "Extended literature classification (Prasad & Bose, 2001 et seq.)",
    "note": "Literature-based, not a regulatory threshold.",
    "thresholds": [
        (25,  "Very Low"),
        (50,  "Low"),
        (75,  "Moderate"),
        (100, "High"),
    ],
    "below_first": "Very Low",
    "above_last": "Critical",
}


def _classify_hpi(hpi: float, profile: str = "mohan") -> tuple[str, str]:
    """Return (classification_label, source_note)."""
    if profile == "extended":
        cfg = _EXTENDED_CLASSIFICATION
        thresholds = cfg["thresholds"]
        for threshold, label in thresholds:
            if hpi < threshold:
                return label, cfg["source"]
        return cfg.get("above_last", "Critical"), cfg["source"]
    else:
        cfg = _MOHAN_CLASSIFICATION
        if hpi < cfg["thresholds"][0][0]:
            return cfg["below_first"], cfg["source"]
        return cfg["thresholds"][0][1], cfg["source"]


# ============================================================ #
#  Core calculation function                                    #
# ============================================================ #

def calculate_hpi(
    measurements: dict[str, float],
    standards: dict[str, float],
    ideal_values: dict[str, float] | None = None,
    bdl_flags: dict[str, bool] | None = None,
    classification_profile: str = "mohan",
) -> HPIResult:
    """
    Compute the Heavy Metal Pollution Index for a single sample.

    Parameters
    ----------
    measurements : dict[str, float]
        Metal symbol → measured concentration in mg/L.
        Example: {"Pb": 0.015, "Cd": 0.002, "Cr": 0.030}

    standards : dict[str, float]
        Metal symbol → reference (permissible) limit in mg/L.
        Only metals present in both `measurements` and `standards` are used.
        Must be > 0. If Si = 0, the metal is excluded with a warning.

    ideal_values : dict[str, float] | None
        Metal symbol → ideal (background) concentration in mg/L.
        Defaults to 0 for all metals (standard practice for drinking water).

    bdl_flags : dict[str, bool] | None
        Metal symbol → True if BDL. BDL metals are excluded from HPI.
        Never converted to zero.

    classification_profile : str
        "mohan" (default) or "extended".

    Returns
    -------
    HPIResult
    """
    if ideal_values is None:
        ideal_values = {}
    if bdl_flags is None:
        bdl_flags = {}

    warnings: list[str] = []
    excluded: dict[str, str] = {}
    per_metal_results: list[MetalHPIResult] = []

    # Identify common metals
    common_metals = set(measurements.keys()) & set(standards.keys())

    for metal in sorted(common_metals):
        Mi = measurements[metal]
        Si = standards[metal]
        Ii = ideal_values.get(metal, 0.0)

        # --- Exclusion checks ---
        if bdl_flags.get(metal, False):
            excluded[metal] = "BDL — below detection limit; excluded from HPI"
            warnings.append(f"{metal}: BDL flag set — excluded from calculation.")
            continue

        if Mi is None or (isinstance(Mi, float) and math.isnan(Mi)):
            excluded[metal] = "Missing measurement"
            warnings.append(f"{metal}: Missing concentration value — excluded.")
            continue

        if Mi < 0:
            excluded[metal] = f"Negative concentration ({Mi} mg/L) — physically invalid"
            warnings.append(f"{metal}: Negative concentration {Mi} — excluded.")
            continue

        if Si is None or Si <= 0:
            excluded[metal] = f"Invalid reference limit ({Si}) — must be > 0"
            warnings.append(f"{metal}: Reference limit {Si} is invalid — excluded.")
            continue

        denominator = abs(Si - Ii)
        if denominator == 0:
            excluded[metal] = "Si equals Ii — denominator is zero"
            warnings.append(f"{metal}: Si == Ii → Qi undefined — excluded.")
            continue

        # --- Compute components ---
        Wi = 1.0 / Si
        Qi = (abs(Mi - Ii) / denominator) * 100.0
        WiQi = Wi * Qi

        per_metal_results.append(
            MetalHPIResult(
                metal=metal,
                measured_concentration=Mi,
                reference_limit=Si,
                ideal_value=Ii,
                weight=Wi,
                sub_index=Qi,
                weighted_numerator=WiQi,
                # These two are filled after aggregation
                effective_contribution=0.0,
                percentage_contribution=0.0,
            )
        )

    if not per_metal_results:
        raise ValueError(
            "No valid metals available for HPI calculation after applying exclusions. "
            f"Excluded: {excluded}. Warnings: {warnings}"
        )

    # --- Aggregate ---
    sum_Wi = sum(r.weight for r in per_metal_results)
    sum_WiQi = sum(r.weighted_numerator for r in per_metal_results)

    if sum_Wi == 0:
        raise ValueError("Sum of weights (ΣWi) is zero — cannot compute HPI.")

    hpi = sum_WiQi / sum_Wi

    # --- Fill effective and percentage contributions ---
    for r in per_metal_results:
        r.effective_contribution = r.weighted_numerator / sum_Wi
        r.percentage_contribution = (
            (r.weighted_numerator / sum_WiQi) * 100.0 if sum_WiQi != 0 else 0.0
        )

    classification, class_source = _classify_hpi(hpi, classification_profile)

    return HPIResult(
        hpi=hpi,
        classification=classification,
        classification_source=class_source,
        metals_used=[r.metal for r in per_metal_results],
        metals_excluded=excluded,
        per_metal=per_metal_results,
        sum_weights=sum_Wi,
        sum_weighted_numerators=sum_WiQi,
        warnings=warnings,
    )


def hpi_result_to_dict(result: HPIResult) -> dict[str, Any]:
    """Serialise HPIResult to a JSON-safe dict."""
    return {
        "hpi": round(result.hpi, 6),
        "classification": result.classification,
        "classification_source": result.classification_source,
        "metals_used": result.metals_used,
        "metals_excluded": result.metals_excluded,
        "sum_weights": round(result.sum_weights, 8),
        "sum_weighted_numerators": round(result.sum_weighted_numerators, 6),
        "warnings": result.warnings,
        "methodology_note": result.methodology_note,
        "per_metal": [
            {
                "metal": r.metal,
                "measured_concentration_mg_L": round(r.measured_concentration, 6),
                "reference_limit_mg_L": round(r.reference_limit, 6),
                "ideal_value_mg_L": round(r.ideal_value, 6),
                "weight_Wi": round(r.weight, 6),
                "sub_index_Qi": round(r.sub_index, 6),
                "weighted_numerator_WiQi": round(r.weighted_numerator, 6),
                "effective_contribution": round(r.effective_contribution, 6),
                "percentage_contribution": round(r.percentage_contribution, 6),
            }
            for r in result.per_metal
        ],
    }
