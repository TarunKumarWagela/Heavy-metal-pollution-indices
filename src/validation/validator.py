"""
Data Validation Engine for HMPIAS
===================================
Validates groundwater sample data before index calculations.

Handles:
- Negative concentration values
- Missing values
- BDL (Below Detection Limit) measurements
- Invalid numeric values
- Duplicate records
- Invalid latitude/longitude
- mg/L vs µg/L unit conversion
- Invalid/zero reference limits

Philosophy:
- Never silently convert BDL to zero
- Preserve original measurements with qualifiers
- Return structured warnings, not silent corrections
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import numpy as np

# ============================================================ #
#  Constants                                                    #
# ============================================================ #

# Standard column names after mapping
STANDARD_COLUMNS = [
    "sample_id", "state", "district", "station",
    "latitude", "longitude", "sample_date",
    "pH", "EC", "TDS",
    "Fe", "As", "U", "Mn", "Cu", "Pb", "Zn", "Ni", "Cd", "Cr",
    "fluoride", "nitrate",
]

METAL_COLUMNS = ["Fe", "As", "U", "Mn", "Cu", "Pb", "Zn", "Ni", "Cd", "Cr"]
NUMERIC_COLUMNS = METAL_COLUMNS + ["pH", "EC", "TDS", "fluoride", "nitrate"]

# BDL sentinel strings (case-insensitive)
BDL_PATTERNS = frozenset({
    "bdl", "bl", "nd", "n.d.", "not detected", "not detectable",
    "below detection", "below detection limit", "bdl", "<dl", "tr", "trace",
})

# Regex for values like "<0.01" or "<DL"
BDL_REGEX = re.compile(r"^<\s*[\d.]+$|^<\s*dl$|^<\s*d\.l\.$", re.IGNORECASE)

# India bounding box (loose)
INDIA_LAT_MIN, INDIA_LAT_MAX = 6.0, 38.0
INDIA_LON_MIN, INDIA_LON_MAX = 68.0, 98.0

# Physical plausibility bounds (mg/L) — these are sanity checks, NOT standards
CONCENTRATION_MAX = {
    "Fe": 50.0, "As": 10.0, "U": 5.0, "Mn": 20.0,
    "Cu": 50.0, "Pb": 5.0, "Zn": 100.0, "Ni": 10.0,
    "Cd": 5.0, "Cr": 10.0,
    "fluoride": 50.0, "nitrate": 500.0,
    "TDS": 50000.0, "EC": 100000.0,
}

# ============================================================ #
#  Result data classes                                          #
# ============================================================ #

@dataclass
class FieldWarning:
    row_index: int | None
    sample_id: str | None
    field: str
    issue: str
    value: Any
    severity: str  # "error" | "warning" | "info"


@dataclass
class ValidationResult:
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    bdl_counts: dict[str, int]            # metal → count of BDL values
    missing_counts: dict[str, int]         # column → count of missing values
    negative_counts: dict[str, int]        # column → count of negatives
    out_of_bounds_coords: int
    warnings: list[FieldWarning] = field(default_factory=list)
    errors: list[FieldWarning] = field(default_factory=list)
    cleaned_df: pd.DataFrame | None = None
    bdl_flag_columns: dict[str, str] = field(default_factory=dict)  # metal → bdl_flag_col

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "invalid_rows": self.invalid_rows,
            "duplicate_rows": self.duplicate_rows,
            "bdl_counts": self.bdl_counts,
            "missing_counts": self.missing_counts,
            "negative_counts": self.negative_counts,
            "out_of_bounds_coords": self.out_of_bounds_coords,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


# ============================================================ #
#  BDL Detection                                               #
# ============================================================ #

def is_bdl(value: Any) -> bool:
    """Return True if `value` is a BDL sentinel string."""
    if value is None:
        return False
    s = str(value).strip().lower()
    if s in BDL_PATTERNS:
        return True
    if BDL_REGEX.match(s):
        return True
    return False


def parse_concentration(value: Any) -> tuple[float | None, bool]:
    """
    Parse a concentration value.

    Returns
    -------
    (numeric_value, is_bdl_flag)
    - If BDL: (None, True)  — never converts to zero
    - If valid number: (float, False)
    - If unparseable: (None, False)  — caller handles as missing
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None, False

    if is_bdl(value):
        return None, True

    try:
        f = float(str(value).strip().replace(",", ""))
        return f, False
    except (ValueError, TypeError):
        return None, False


# ============================================================ #
#  Unit Conversion                                             #
# ============================================================ #

def convert_ug_to_mg(value: float) -> float:
    """Convert µg/L to mg/L (divide by 1000)."""
    return value / 1000.0


def detect_unit_scale_issue(metal: str, value: float) -> str | None:
    """
    Heuristically detect possible µg/L values reported as mg/L.

    Returns a warning string if the value exceeds a plausible mg/L maximum
    by more than 10×, suggesting possible unit mismatch.
    """
    max_plausible = CONCENTRATION_MAX.get(metal)
    if max_plausible and value > max_plausible * 10:
        return (
            f"{metal}: value {value} mg/L far exceeds plausible range "
            f"(max ~{max_plausible} mg/L). Possible µg/L–mg/L unit mismatch."
        )
    return None


# ============================================================ #
#  Core Validation Function                                    #
# ============================================================ #

def validate_dataframe(
    df: pd.DataFrame,
    check_india_bounds: bool = True,
    flag_duplicates: bool = True,
) -> ValidationResult:
    """
    Validate a groundwater sample DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with standardised column names.
    check_india_bounds : bool
        Flag coordinates outside India's loose bounding box.
    flag_duplicates : bool
        Flag duplicate sample_id values.

    Returns
    -------
    ValidationResult
    """
    total_rows = len(df)
    warnings_list: list[FieldWarning] = []
    errors_list: list[FieldWarning] = []

    # Work on a copy
    cleaned = df.copy()

    # Track BDL flags per metal
    bdl_flag_columns: dict[str, str] = {}
    bdl_counts: dict[str, int] = {}
    missing_counts: dict[str, int] = {}
    negative_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # 1. Parse metal concentrations, detect BDL
    # ------------------------------------------------------------------
    for metal in METAL_COLUMNS:
        if metal not in cleaned.columns:
            missing_counts[metal] = total_rows
            warnings_list.append(FieldWarning(
                row_index=None, sample_id=None, field=metal,
                issue=f"Column '{metal}' not present in dataset",
                value=None, severity="warning"
            ))
            continue

        bdl_flag_col = f"{metal}_bdl"
        bdl_flag_columns[metal] = bdl_flag_col
        cleaned[bdl_flag_col] = False

        bdl_count = 0
        missing_count = 0
        neg_count = 0

        parsed_values = []
        bdl_flags_col = []

        for idx, raw_val in enumerate(cleaned[metal]):
            sample_id = cleaned.get("sample_id", pd.Series([None] * total_rows))[idx]

            numeric_val, is_bdl_flag = parse_concentration(raw_val)

            if is_bdl_flag:
                bdl_count += 1
                parsed_values.append(None)
                bdl_flags_col.append(True)
                warnings_list.append(FieldWarning(
                    row_index=idx, sample_id=str(sample_id),
                    field=metal,
                    issue="BDL (below detection limit) — value preserved as NaN with BDL flag",
                    value=raw_val, severity="info"
                ))
            elif numeric_val is None:
                missing_count += 1
                parsed_values.append(None)
                bdl_flags_col.append(False)
                if raw_val is not None and str(raw_val).strip() not in ("", "nan", "NaN", "None"):
                    errors_list.append(FieldWarning(
                        row_index=idx, sample_id=str(sample_id),
                        field=metal,
                        issue=f"Unparseable value '{raw_val}' — treated as missing",
                        value=raw_val, severity="error"
                    ))
            else:
                if numeric_val < 0:
                    neg_count += 1
                    errors_list.append(FieldWarning(
                        row_index=idx, sample_id=str(sample_id),
                        field=metal,
                        issue=f"Negative concentration {numeric_val} mg/L — physically invalid",
                        value=numeric_val, severity="error"
                    ))
                    parsed_values.append(numeric_val)
                    bdl_flags_col.append(False)
                else:
                    # Unit scale check
                    scale_warn = detect_unit_scale_issue(metal, numeric_val)
                    if scale_warn:
                        warnings_list.append(FieldWarning(
                            row_index=idx, sample_id=str(sample_id),
                            field=metal, issue=scale_warn,
                            value=numeric_val, severity="warning"
                        ))
                    parsed_values.append(numeric_val)
                    bdl_flags_col.append(False)

        cleaned[metal] = parsed_values
        cleaned[bdl_flag_col] = bdl_flags_col
        bdl_counts[metal] = bdl_count
        missing_counts[metal] = missing_count
        negative_counts[metal] = neg_count

    # ------------------------------------------------------------------
    # 2. Validate pH
    # ------------------------------------------------------------------
    if "pH" in cleaned.columns:
        for idx, val in enumerate(cleaned["pH"]):
            try:
                f = float(val)
                if not (0 <= f <= 14):
                    errors_list.append(FieldWarning(
                        row_index=idx, sample_id=None, field="pH",
                        issue=f"pH {f} outside valid range [0, 14]",
                        value=f, severity="error"
                    ))
            except (TypeError, ValueError):
                pass

    # ------------------------------------------------------------------
    # 3. Validate coordinates
    # ------------------------------------------------------------------
    out_of_bounds = 0
    if "latitude" in cleaned.columns and "longitude" in cleaned.columns:
        for idx in range(total_rows):
            raw_lat = cleaned["latitude"].iloc[idx]
            raw_lon = cleaned["longitude"].iloc[idx]

            # If coordinates are blank/NaN, they are optional metadata - do not fail the row
            if pd.isna(raw_lat) or pd.isna(raw_lon) or raw_lat == "" or raw_lon == "":
                continue

            try:
                lat = float(raw_lat)
                lon = float(raw_lon)
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    errors_list.append(FieldWarning(
                        row_index=idx, sample_id=None, field="coordinates",
                        issue=f"Invalid coordinates ({lat}, {lon})",
                        value=(lat, lon), severity="error"
                    ))
                    out_of_bounds += 1
                elif check_india_bounds:
                    if not (INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX and
                            INDIA_LON_MIN <= lon <= INDIA_LON_MAX):
                        warnings_list.append(FieldWarning(
                            row_index=idx, sample_id=None, field="coordinates",
                            issue=f"Coordinates ({lat}, {lon}) outside India bounding box",
                            value=(lat, lon), severity="warning"
                        ))
                        out_of_bounds += 1
            except (TypeError, ValueError):
                errors_list.append(FieldWarning(
                    row_index=idx, sample_id=None, field="coordinates",
                    issue=f"Unparseable coordinates ({raw_lat}, {raw_lon})",
                    value=(raw_lat, raw_lon), severity="error"
                ))
                out_of_bounds += 1

    # ------------------------------------------------------------------
    # 4. Duplicates
    # ------------------------------------------------------------------
    dup_count = 0
    if flag_duplicates and "sample_id" in cleaned.columns:
        dupes = cleaned[cleaned["sample_id"].duplicated(keep=False) &
                        cleaned["sample_id"].notna()]
        dup_count = len(dupes)
        if dup_count > 0:
            warnings_list.append(FieldWarning(
                row_index=None, sample_id=None, field="sample_id",
                issue=f"{dup_count} rows have duplicate sample_id values",
                value=dup_count, severity="warning"
            ))

    # ------------------------------------------------------------------
    # 5. Count valid/invalid rows
    # ------------------------------------------------------------------
    # A row is "invalid" if it has any error-level issue
    error_rows = set(e.row_index for e in errors_list if e.row_index is not None)
    invalid_rows = len(error_rows)
    valid_rows = total_rows - invalid_rows

    return ValidationResult(
        total_rows=total_rows,
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        duplicate_rows=dup_count,
        bdl_counts=bdl_counts,
        missing_counts=missing_counts,
        negative_counts=negative_counts,
        out_of_bounds_coords=out_of_bounds,
        warnings=warnings_list,
        errors=errors_list,
        cleaned_df=cleaned,
        bdl_flag_columns=bdl_flag_columns,
    )


def validate_standards_for_calculation(
    standards: dict[str, float],
) -> list[str]:
    """
    Validate that reference limits are suitable for index calculation.

    Returns a list of issue strings (empty if all OK).
    """
    issues = []
    for metal, limit in standards.items():
        if limit is None:
            issues.append(f"{metal}: Reference limit is None — cannot calculate index")
        elif isinstance(limit, float) and math.isnan(limit):
            issues.append(f"{metal}: Reference limit is NaN")
        elif limit <= 0:
            issues.append(f"{metal}: Reference limit {limit} ≤ 0 — invalid for calculation")
    return issues
