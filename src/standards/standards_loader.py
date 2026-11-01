"""
Standards Loader for HMPIAS
=============================
Loads water quality standard profiles from the database and
provides them in a format suitable for index calculations.
"""

from __future__ import annotations

from typing import Any


# Standard profile identifiers
PROFILE_BIS = "BIS IS 10500"
PROFILE_WHO = "WHO GDWQ"


def get_standards_for_profile(
    profile_name: str,
    metals: list[str] | None = None,
) -> dict[str, float]:
    """
    Fetch reference limits from the database for a given standard profile.

    Returns
    -------
    dict[str, float]
        metal symbol → reference limit in mg/L
        (permissible_limit → guideline_value → acceptable_limit, in priority order)

    Raises
    ------
    ValueError if no standards found for the profile.
    """
    from app.models import WaterStandard

    query = WaterStandard.query.filter_by(standard_name=profile_name)
    if metals:
        query = query.filter(WaterStandard.metal.in_(metals))

    standards = query.all()

    if not standards:
        raise ValueError(
            f"No standards found for profile '{profile_name}'. "
            "Ensure the database has been seeded."
        )

    result: dict[str, float] = {}
    for s in standards:
        limit = s.get_reference_limit()
        if limit is not None and limit > 0:
            result[s.metal] = limit

    return result


def get_all_profiles() -> list[dict[str, Any]]:
    """Return summary of all available standard profiles."""
    from app.models import WaterStandard
    from sqlalchemy import distinct

    profiles = (
        WaterStandard.query
        .with_entities(
            WaterStandard.standard_name,
            WaterStandard.version,
        )
        .distinct()
        .all()
    )
    return [
        {"standard_name": p.standard_name, "version": p.version}
        for p in profiles
    ]


def get_standards_table(profile_name: str) -> list[dict[str, Any]]:
    """Return all limits for a given profile as a list of dicts."""
    from app.models import WaterStandard

    standards = WaterStandard.query.filter_by(standard_name=profile_name).all()
    return [
        {
            "metal": s.metal,
            "parameter": s.parameter,
            "chemical_species": s.chemical_species,
            "acceptable_limit": s.acceptable_limit,
            "permissible_limit": s.permissible_limit,
            "guideline_value": s.guideline_value,
            "unit": s.unit,
            "version": s.version,
            "notes": s.notes,
        }
        for s in standards
    ]
