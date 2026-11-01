"""Dataset service — handles upload, column mapping, validation and ingestion."""

from __future__ import annotations

import io
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any
from werkzeug.utils import secure_filename

import pandas as pd

from app.models import DatasetUpload, Sample, db
from src.validation.validator import validate_dataframe, STANDARD_COLUMNS, METAL_COLUMNS

SAMPLE_CSV_TEMPLATE = """sample_id,state,district,station,latitude,longitude,sample_date,pH,EC,TDS,Fe,As,U,Mn,Cu,Pb,Zn,Ni,Cd,Cr,fluoride,nitrate
GW-001,Rajasthan,Jaipur,Station-A,26.9124,75.7873,2024-01-15,7.2,850,520,0.15,0.008,0.02,0.08,0.04,0.012,1.2,0.015,0.001,0.025,0.8,38
GW-002,Bihar,Patna,Station-B,25.5941,85.1376,2024-01-16,7.8,1200,780,0.45,0.025,0.05,0.22,0.08,0.032,2.1,0.042,0.003,0.048,1.2,55
GW-003,West Bengal,Murshidabad,Station-C,24.1793,88.2719,2024-01-17,6.9,620,410,0.28,0.045,0.01,0.15,0.02,0.018,0.8,0.028,0.001,0.035,0.5,22
GW-004,Uttar Pradesh,Varanasi,Station-D,25.3176,82.9739,2024-01-18,7.4,980,650,0.35,0.012,0.03,0.18,0.06,0.025,1.8,0.035,0.002,0.040,0.9,42
GW-005,Punjab,Amritsar,Station-E,31.6340,74.8723,2024-01-19,7.1,760,480,0.12,0.005,BDL,0.06,0.03,0.008,0.9,0.012,BDL,0.018,0.6,28
"""


def allowed_file(filename: str, allowed_extensions: set[str]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_uploaded_file(file_storage, upload_folder: str) -> tuple[str, str]:
    """Save an uploaded file safely with a UUID prefix. Returns (filepath, safe_original_name)."""
    safe_name = secure_filename(file_storage.filename or "uploaded_dataset")
    ext = Path(safe_name).suffix.lower()
    if not ext:
        ext = ".csv"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_dir = Path(upload_folder).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / unique_name
    file_storage.save(str(file_path))
    return str(file_path), safe_name


def read_uploaded_file(file_path: str) -> pd.DataFrame:
    """Read CSV or Excel file into a DataFrame."""
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        return pd.read_csv(file_path, low_memory=False)
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


# Common aliases for automatic column standardisation
AUTO_COLUMN_ALIASES = {
    # Station / Monitoring Location
    "monitoring_location": "station", "monitoring_station": "station",
    "location": "station", "station_name": "station", "site": "station",
    # Administrative Boundaries
    "state": "state", "province": "state",
    "district": "district", "city": "district", "county": "district",
    # Geographical Coordinates
    "latitude": "latitude", "lat": "latitude", "latitude_simulated": "latitude",
    "longitude": "longitude", "long": "longitude", "lon": "longitude", "longitude_simulated": "longitude",
    # Sampling Date
    "sample_date": "sample_date", "sampling_date": "sample_date", "date": "sample_date",
    # Physical / Chemical Parameters
    "ph": "pH",
    "electrical_conductivity_us_cm": "EC", "electrical_conductivity": "EC", "ec": "EC", "ec_us_cm": "EC",
    "tds_mg_l": "TDS", "tds": "TDS", "total_dissolved_solids": "TDS",
    "fluoride_mg_l": "fluoride", "fluoride": "fluoride", "f": "fluoride",
    "nitrate_mg_l": "nitrate", "nitrate": "nitrate", "no3": "nitrate",
    # Heavy Metals (mg/L)
    "pb_mg_l": "Pb", "pb": "Pb", "lead": "Pb", "lead_mg_l": "Pb",
    "cd_mg_l": "Cd", "cd": "Cd", "cadmium": "Cd", "cadmium_mg_l": "Cd",
    "cr_mg_l": "Cr", "cr": "Cr", "chromium": "Cr", "chromium_mg_l": "Cr",
    "cr_total_mg_l": "Cr", "cr_total": "Cr", "total_chromium": "Cr",
    "fe_mg_l": "Fe", "fe": "Fe", "iron": "Fe", "iron_mg_l": "Fe",
    "as_mg_l": "As", "as": "As", "arsenic": "As", "arsenic_mg_l": "As",
    "u_mg_l": "U", "u": "U", "uranium": "U", "uranium_mg_l": "U",
    "mn_mg_l": "Mn", "mn": "Mn", "manganese": "Mn", "manganese_mg_l": "Mn",
    "cu_mg_l": "Cu", "cu": "Cu", "copper": "Cu", "copper_mg_l": "Cu",
    "zn_mg_l": "Zn", "zn": "Zn", "zinc": "Zn", "zinc_mg_l": "Zn",
    "ni_mg_l": "Ni", "ni": "Ni", "nickel": "Ni", "nickel_mg_l": "Ni",
}


def auto_map_columns(columns: list[str]) -> dict[str, str]:
    """Infer mapping from file column names to standard fields."""
    mapping = {}
    lower_cols = {str(c).strip().lower().replace(" ", "_").replace("-", "_"): c for c in columns}

    # Standard columns priority order
    standard_direct = [
        ("sample_id", ["sample_id", "id", "sample"]),
        ("station", ["station", "monitoring_location", "monitoring_station", "location", "station_name", "site"]),
        ("state", ["state", "province"]),
        ("district", ["district", "city", "county"]),
        ("latitude", ["latitude", "lat", "latitude_simulated"]),
        ("longitude", ["longitude", "long", "lon", "longitude_simulated"]),
        ("sample_date", ["sample_date", "sampling_date", "date"]),
        ("pH", ["ph"]),
        ("EC", ["ec", "electrical_conductivity_us_cm", "electrical_conductivity", "ec_us_cm"]),
        ("TDS", ["tds", "tds_mg_l", "total_dissolved_solids"]),
        ("fluoride", ["fluoride", "fluoride_mg_l", "f"]),
        ("nitrate", ["nitrate", "nitrate_mg_l", "no3"]),
    ]

    for std, aliases in standard_direct:
        for alias in aliases:
            if alias in lower_cols:
                mapping[lower_cols[alias]] = std
                break

    # Heavy metals
    for col in columns:
        cleaned = str(col).strip().lower().replace(" ", "_").replace("-", "_")
        if cleaned in AUTO_COLUMN_ALIASES:
            standard = AUTO_COLUMN_ALIASES[cleaned]
            if standard not in mapping.values():
                mapping[col] = standard

    return mapping


def apply_column_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """
    Rename DataFrame columns using user-provided mapping.

    mapping = { "source_column_name": "standard_column_name" }
    """
    return df.rename(columns=mapping)


def ingest_validated_data(
    cleaned_df: pd.DataFrame,
    upload_record: DatasetUpload,
    bdl_flag_columns: dict[str, str],
) -> int:
    """
    Insert validated sample rows into the database.
    Returns the number of rows successfully inserted.
    """
    inserted = 0

    for _, row in cleaned_df.iterrows():
        # Parse date
        sample_date = None
        if "sample_date" in cleaned_df.columns and pd.notna(row.get("sample_date")):
            try:
                sample_date = pd.to_datetime(row["sample_date"]).date()
            except Exception:
                sample_date = None

        def get_float(col: str) -> float | None:
            v = row.get(col)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        def get_bool(col: str) -> bool:
            v = row.get(col)
            if v is None:
                return False
            return bool(v)

        sample = Sample(
            upload_id=upload_record.id,
            sample_id=str(row.get("sample_id", "")) or None,
            state=str(row.get("state", "")) or None,
            district=str(row.get("district", "")) or None,
            station=str(row.get("station", "")) or None,
            latitude=get_float("latitude"),
            longitude=get_float("longitude"),
            sample_date=sample_date,
            pH=get_float("pH"),
            EC=get_float("EC"),
            TDS=get_float("TDS"),
            fluoride=get_float("fluoride"),
            nitrate=get_float("nitrate"),
            Fe=get_float("Fe"), Fe_bdl=get_bool(bdl_flag_columns.get("Fe", "Fe_bdl")),
            As=get_float("As"), As_bdl=get_bool(bdl_flag_columns.get("As", "As_bdl")),
            U=get_float("U"),   U_bdl=get_bool(bdl_flag_columns.get("U", "U_bdl")),
            Mn=get_float("Mn"), Mn_bdl=get_bool(bdl_flag_columns.get("Mn", "Mn_bdl")),
            Cu=get_float("Cu"), Cu_bdl=get_bool(bdl_flag_columns.get("Cu", "Cu_bdl")),
            Pb=get_float("Pb"), Pb_bdl=get_bool(bdl_flag_columns.get("Pb", "Pb_bdl")),
            Zn=get_float("Zn"), Zn_bdl=get_bool(bdl_flag_columns.get("Zn", "Zn_bdl")),
            Ni=get_float("Ni"), Ni_bdl=get_bool(bdl_flag_columns.get("Ni", "Ni_bdl")),
            Cd=get_float("Cd"), Cd_bdl=get_bool(bdl_flag_columns.get("Cd", "Cd_bdl")),
            Cr=get_float("Cr"), Cr_bdl=get_bool(bdl_flag_columns.get("Cr", "Cr_bdl")),
        )
        db.session.add(sample)
        inserted += 1

    db.session.commit()
    return inserted


def process_upload(
    file_storage,
    column_mapping: dict[str, str],
    upload_folder: str,
    notes: str = "",
) -> dict[str, Any]:
    """
    Full upload pipeline: save → read → map → validate → ingest.

    Returns a dict with upload_id, validation_summary, row_counts, warnings.
    """
    # 1. Save file
    file_path, original_name = save_uploaded_file(file_storage, upload_folder)

    # 2. Create upload record (pending)
    upload = DatasetUpload(
        filename=Path(file_path).name,
        original_filename=original_name,
        file_path=file_path,
        file_size_bytes=Path(file_path).stat().st_size,
        processing_status="pending",
        column_mapping=column_mapping,
        notes=notes,
    )
    db.session.add(upload)
    db.session.flush()  # get upload.id

    try:
        # 3. Read
        df = read_uploaded_file(file_path)
        upload.row_count = len(df)
        upload.column_count = len(df.columns)

        # 4. Apply column mapping (merge auto-detected aliases with any user mappings)
        merged_mapping = auto_map_columns(list(df.columns))
        if column_mapping:
            merged_mapping.update(column_mapping)
        if merged_mapping:
            df = apply_column_mapping(df, merged_mapping)
            upload.column_mapping = merged_mapping

        # 5. Validate
        validation_result = validate_dataframe(df)
        upload.validation_summary = validation_result.summary
        upload.processing_status = "validated"

        # 6. Ingest
        inserted = ingest_validated_data(
            validation_result.cleaned_df,
            upload,
            validation_result.bdl_flag_columns,
        )
        upload.processing_status = "processed"
        db.session.commit()

        return {
            "upload_id": upload.id,
            "original_filename": original_name,
            "rows_in_file": len(df),
            "rows_inserted": inserted,
            "validation_summary": validation_result.summary,
            "warnings": [
                {"field": w.field, "issue": w.issue, "severity": w.severity}
                for w in validation_result.warnings[:50]
            ],
            "errors": [
                {"field": e.field, "issue": e.issue, "severity": e.severity}
                for e in validation_result.errors[:50]
            ],
        }

    except Exception as exc:
        upload.processing_status = "error"
        db.session.commit()
        raise RuntimeError(f"Upload processing failed: {exc}") from exc
