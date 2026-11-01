"""
Calculation Service — orchestrates HPI, HEI, and Degree of Contamination
calculations for samples stored in the database.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models import (
    IndexResult, MetalContribution, Sample, CalculationMethodology, db,
)
from src.indices.hpi import calculate_hpi, hpi_result_to_dict
from src.indices.hei import calculate_hei, hei_result_to_dict
from src.indices.degree_of_contamination import (
    calculate_degree_of_contamination, cd_result_to_dict,
)
from src.standards.standards_loader import get_standards_for_profile
from src.validation.validator import validate_standards_for_calculation

logger = logging.getLogger(__name__)

METAL_COLUMNS = ["Fe", "As", "U", "Mn", "Cu", "Pb", "Zn", "Ni", "Cd", "Cr"]


def _sample_to_measurements(sample: Sample) -> tuple[dict, dict]:
    """Extract measurements and BDL flags from a Sample ORM object."""
    measurements: dict[str, float] = {}
    bdl_flags: dict[str, bool] = {}
    for metal in METAL_COLUMNS:
        val = getattr(sample, metal, None)
        bdl = getattr(sample, f"{metal}_bdl", False)
        if val is not None:
            measurements[metal] = val
        bdl_flags[metal] = bool(bdl)
    return measurements, bdl_flags


def calculate_indices_for_sample(
    sample_id: int,
    standard_profile: str = "BIS IS 10500",
    index_types: list[str] | None = None,
    non_negative_cd: bool = False,
) -> dict[str, Any]:
    """
    Calculate HPI, HEI, and/or Degree of Contamination for one sample.

    Parameters
    ----------
    sample_id : int  — DB id of the Sample record
    standard_profile : str  — name of the WaterStandard profile to use
    index_types : list[str] | None  — ["HPI","HEI","Cd_index"] or None=all
    non_negative_cd : bool  — use non-negative variant for Cd_index

    Returns
    -------
    dict with per-index results and any warnings
    """
    if index_types is None:
        index_types = ["HPI", "HEI", "Cd_index"]

    sample = db.session.get(Sample, sample_id)
    if sample is None:
        raise ValueError(f"Sample {sample_id} not found.")

    measurements, bdl_flags = _sample_to_measurements(sample)

    # Load standards (only for metals that have measurements)
    try:
        standards = get_standards_for_profile(
            standard_profile,
            metals=list(measurements.keys()),
        )
    except ValueError as e:
        raise ValueError(str(e)) from e

    # Validate standards
    issues = validate_standards_for_calculation(standards)
    if issues:
        logger.warning("Standard issues for %s: %s", standard_profile, issues)

    results: dict[str, Any] = {
        "sample_id": sample_id,
        "sample_label": sample.sample_id,
        "standard_profile": standard_profile,
        "indices": {},
        "global_warnings": issues,
    }

    # ---- HPI ----
    if "HPI" in index_types:
        try:
            hpi_result = calculate_hpi(
                measurements=measurements,
                standards=standards,
                bdl_flags=bdl_flags,
            )
            hpi_dict = hpi_result_to_dict(hpi_result)
            results["indices"]["HPI"] = hpi_dict

            # Persist to database
            ir = IndexResult(
                sample_id=sample_id,
                standard_profile=standard_profile,
                index_type="HPI",
                index_value=hpi_result.hpi,
                classification=hpi_result.classification,
                metals_included=hpi_result.metals_used,
                metals_excluded=hpi_result.metals_excluded,
                calculation_inputs={
                    m: {"measured": measurements.get(m), "standard": standards.get(m)}
                    for m in hpi_result.metals_used
                },
                methodology_notes=hpi_result.methodology_note,
            )
            db.session.add(ir)
            db.session.flush()

            # Per-metal contributions
            for pm in hpi_result.per_metal:
                mc = MetalContribution(
                    index_result_id=ir.id,
                    metal=pm.metal,
                    measured_concentration=pm.measured_concentration,
                    reference_limit=pm.reference_limit,
                    ideal_value=pm.ideal_value,
                    weight=pm.weight,
                    sub_index=pm.sub_index,
                    weighted_numerator=pm.weighted_numerator,
                    effective_contribution=pm.effective_contribution,
                    percentage_contribution=pm.percentage_contribution,
                )
                db.session.add(mc)

        except ValueError as e:
            results["indices"]["HPI"] = {"error": str(e)}

    # ---- HEI ----
    if "HEI" in index_types:
        try:
            hei_result = calculate_hei(
                measurements=measurements,
                standards=standards,
                bdl_flags=bdl_flags,
            )
            results["indices"]["HEI"] = hei_result_to_dict(hei_result)

            ir = IndexResult(
                sample_id=sample_id,
                standard_profile=standard_profile,
                index_type="HEI",
                index_value=hei_result.hei,
                classification=hei_result.classification,
                metals_included=hei_result.metals_used,
                metals_excluded=hei_result.metals_excluded,
                methodology_notes=hei_result.methodology_note,
            )
            db.session.add(ir)

        except ValueError as e:
            results["indices"]["HEI"] = {"error": str(e)}

    # ---- Degree of Contamination ----
    if "Cd_index" in index_types:
        try:
            cd_result = calculate_degree_of_contamination(
                measurements=measurements,
                reference_values=standards,
                bdl_flags=bdl_flags,
                non_negative=non_negative_cd,
            )
            results["indices"]["Cd_index"] = cd_result_to_dict(cd_result)

            ir = IndexResult(
                sample_id=sample_id,
                standard_profile=standard_profile,
                index_type="Cd_index",
                index_value=cd_result.cd_index,
                classification=cd_result.classification,
                metals_included=cd_result.metals_used,
                metals_excluded=cd_result.metals_excluded,
                methodology_notes=cd_result.methodology_note,
            )
            db.session.add(ir)

        except ValueError as e:
            results["indices"]["Cd_index"] = {"error": str(e)}

    db.session.commit()
    return results


def calculate_for_dataset(
    upload_id: int,
    standard_profile: str = "BIS IS 10500",
    index_types: list[str] | None = None,
) -> dict[str, Any]:
    """Calculate indices for all samples in an upload."""
    from app.models import Sample
    samples = Sample.query.filter_by(upload_id=upload_id).all()

    if not samples:
        raise ValueError(f"No samples found for upload_id={upload_id}")

    all_results = []
    errors = []

    for sample in samples:
        try:
            result = calculate_indices_for_sample(
                sample_id=sample.id,
                standard_profile=standard_profile,
                index_types=index_types,
            )
            all_results.append(result)
        except Exception as exc:
            errors.append({"sample_id": sample.id, "error": str(exc)})

    return {
        "upload_id": upload_id,
        "total_samples": len(samples),
        "calculated": len(all_results),
        "errors": errors,
        "results": all_results,
    }
