"""
HMPIAS — SQLAlchemy ORM Models
================================
All database tables for the Heavy Metal Pollution Index Assessment System.

Design notes
------------
* Authentication is excluded from MVP. User-facing fields use a nullable
  `uploaded_by` VARCHAR so the schema is forward-compatible.
* `Cd` in variable names ALWAYS means cadmium (element symbol).
  The Degree of Contamination index is stored as `deg_contamination`.
* Every calculation result records which standard version was used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================ #
#  Helper: JSON column stored as TEXT for SQLite compatibility  #
# ============================================================ #

class JSONType(db.TypeDecorator):  # type: ignore[type-arg]
    """Store Python dicts/lists as JSON text (SQLite-safe)."""

    impl = db.Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:  # noqa: ANN401
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value: str | None, dialect: Any) -> Any:  # noqa: ANN401
        if value is not None:
            return json.loads(value)
        return None


# ============================================================ #
#  DatasetUpload                                                #
# ============================================================ #

class DatasetUpload(db.Model):
    """Tracks every CSV/Excel file uploaded by users."""

    __tablename__ = "dataset_uploads"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    original_filename = db.Column(db.String(256), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_size_bytes = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    uploaded_by = db.Column(db.String(128), nullable=True)  # future auth hook
    row_count = db.Column(db.Integer)
    column_count = db.Column(db.Integer)
    processing_status = db.Column(
        db.String(32), default="pending"
    )  # pending | validated | processed | error
    validation_summary = db.Column(JSONType)
    column_mapping = db.Column(JSONType)
    notes = db.Column(db.Text)

    # Relationships
    samples = db.relationship(
        "Sample", backref="upload", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DatasetUpload id={self.id} file={self.original_filename}>"


# ============================================================ #
#  WaterStandard                                                #
# ============================================================ #

class WaterStandard(db.Model):
    """
    Regulatory / guideline limits for drinking water.

    Sources currently seeded:
      * BIS IS 10500:2012 (amended 2019)
      * WHO Guidelines for Drinking-water Quality, 4th ed. (2022)

    Fields
    ------
    acceptable_limit : float | None
        The desirable / acceptable upper limit (BIS terminology).
        If not specified by the standard, NULL.
    permissible_limit : float | None
        The maximum permissible limit in absence of better source.
        If not specified (e.g. WHO uses a single guideline value), NULL.
    guideline_value : float | None
        Used for WHO-style single-value guidelines.
    unit : str
        Always stored normalised to mg/L.
    chemical_species : str
        Specifies form, e.g. "total", "Cr(VI)", "As(III+V)".
    """

    __tablename__ = "water_standards"

    id = db.Column(db.Integer, primary_key=True)
    standard_name = db.Column(db.String(128), nullable=False)
    version = db.Column(db.String(64))
    metal = db.Column(db.String(32), nullable=False)  # e.g. "Pb", "As"
    parameter = db.Column(db.String(64))  # human label e.g. "Lead"
    chemical_species = db.Column(db.String(64), default="total")
    acceptable_limit = db.Column(db.Float, nullable=True)
    permissible_limit = db.Column(db.Float, nullable=True)
    guideline_value = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(16), default="mg/L")
    source_url = db.Column(db.String(512))
    effective_date = db.Column(db.String(16))
    notes = db.Column(db.Text)

    def __repr__(self) -> str:
        return (
            f"<WaterStandard {self.standard_name} {self.metal} "
            f"perm={self.permissible_limit} {self.unit}>"
        )

    def get_reference_limit(self) -> float | None:
        """
        Return the single reference value used for index calculations.

        Priority: permissible_limit → guideline_value → acceptable_limit.
        Returns None if no limit is defined.

        NOTE: Uses explicit ``is not None`` checks so that a valid 0.0 limit
        is never silently discarded by Python's falsy ``or`` short-circuit.
        """
        for limit in (self.permissible_limit, self.guideline_value, self.acceptable_limit):
            if limit is not None:
                return limit
        return None


# ============================================================ #
#  Sample                                                       #
# ============================================================ #

class Sample(db.Model):
    """
    A single groundwater sample observation.

    Field names follow CGWB / NWDP conventions where possible.
    All concentration fields are stored in mg/L (normalised at ingestion).
    BDL (below detection limit) flags are stored separately.
    """

    __tablename__ = "samples"

    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(
        db.Integer, db.ForeignKey("dataset_uploads.id"), nullable=False
    )
    sample_id = db.Column(db.String(128))  # source identifier
    state = db.Column(db.String(64))
    district = db.Column(db.String(64))
    station = db.Column(db.String(128))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    sample_date = db.Column(db.Date)

    # General parameters
    pH = db.Column(db.Float)
    EC = db.Column(db.Float)   # µS/cm
    TDS = db.Column(db.Float)  # mg/L
    fluoride = db.Column(db.Float)   # mg/L
    nitrate = db.Column(db.Float)    # mg/L

    # Heavy metals (mg/L)
    Fe = db.Column(db.Float)
    As = db.Column(db.Float)
    U = db.Column(db.Float)
    Mn = db.Column(db.Float)
    Cu = db.Column(db.Float)
    Pb = db.Column(db.Float)
    Zn = db.Column(db.Float)
    Ni = db.Column(db.Float)
    Cd = db.Column(db.Float)   # cadmium — NOT Degree of Contamination
    Cr = db.Column(db.Float)

    # BDL flags (True if the measured value is below detection limit)
    Fe_bdl = db.Column(db.Boolean, default=False)
    As_bdl = db.Column(db.Boolean, default=False)
    U_bdl = db.Column(db.Boolean, default=False)
    Mn_bdl = db.Column(db.Boolean, default=False)
    Cu_bdl = db.Column(db.Boolean, default=False)
    Pb_bdl = db.Column(db.Boolean, default=False)
    Zn_bdl = db.Column(db.Boolean, default=False)
    Ni_bdl = db.Column(db.Boolean, default=False)
    Cd_bdl = db.Column(db.Boolean, default=False)
    Cr_bdl = db.Column(db.Boolean, default=False)

    # Data-quality metadata
    data_quality_flags = db.Column(JSONType)  # list of warning strings
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    # Relationships
    index_results = db.relationship(
        "IndexResult", backref="sample", lazy="dynamic", cascade="all, delete-orphan"
    )
    predictions = db.relationship(
        "Prediction", backref="sample", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Sample id={self.id} sample_id={self.sample_id} state={self.state}>"

    def to_dict(self) -> dict:
        metals = ["Fe", "As", "U", "Mn", "Cu", "Pb", "Zn", "Ni", "Cd", "Cr"]
        result = {
            "id": self.id,
            "sample_id": self.sample_id,
            "state": self.state,
            "district": self.district,
            "station": self.station,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "sample_date": self.sample_date.isoformat() if self.sample_date else None,
            "pH": self.pH,
            "EC": self.EC,
            "TDS": self.TDS,
            "fluoride": self.fluoride,
            "nitrate": self.nitrate,
        }
        for m in metals:
            result[m] = getattr(self, m)
            result[f"{m}_bdl"] = getattr(self, f"{m}_bdl")
        return result


# ============================================================ #
#  IndexResult                                                  #
# ============================================================ #

class IndexResult(db.Model):
    """
    Computed pollution-index values for one sample under one standard set.

    index_type : str
        One of: 'HPI', 'HEI', 'Cd_index'
        (Using 'Cd_index' to avoid confusion with Cd metal)
    """

    __tablename__ = "index_results"

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey("samples.id"), nullable=False)
    standard_profile = db.Column(db.String(64))  # e.g. "BIS_IS10500_2012"
    index_type = db.Column(db.String(32), nullable=False)  # HPI | HEI | Cd_index
    index_value = db.Column(db.Float)
    classification = db.Column(db.String(64))
    metals_included = db.Column(JSONType)     # list of metal symbols used
    metals_excluded = db.Column(JSONType)     # metals skipped (BDL, missing, no standard)
    calculation_inputs = db.Column(JSONType)  # detailed per-metal inputs
    methodology_notes = db.Column(db.Text)
    calculated_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    # Relationships
    contributions = db.relationship(
        "MetalContribution",
        backref="index_result",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<IndexResult id={self.id} type={self.index_type} "
            f"value={self.index_value:.4f}>"
        )


# ============================================================ #
#  MetalContribution                                            #
# ============================================================ #

class MetalContribution(db.Model):
    """
    Per-metal breakdown for a computed index (primarily used for HPI).

    effective_contribution : float
        (Wi * Qi) / sum(Wi)  — contributions sum to HPI value.
    percentage_contribution : float
        (Wi * Qi) / sum(Wi * Qi) * 100  — sums to 100 %.
    """

    __tablename__ = "metal_contributions"

    id = db.Column(db.Integer, primary_key=True)
    index_result_id = db.Column(
        db.Integer, db.ForeignKey("index_results.id"), nullable=False
    )
    metal = db.Column(db.String(16), nullable=False)
    measured_concentration = db.Column(db.Float)
    reference_limit = db.Column(db.Float)    # Si (permissible)
    ideal_value = db.Column(db.Float)        # Ii (typically 0 for metals)
    weight = db.Column(db.Float)             # Wi = 1/Si
    sub_index = db.Column(db.Float)          # Qi
    weighted_numerator = db.Column(db.Float) # Wi * Qi
    effective_contribution = db.Column(db.Float)
    percentage_contribution = db.Column(db.Float)

    def __repr__(self) -> str:
        return (
            f"<MetalContribution metal={self.metal} "
            f"pct={self.percentage_contribution:.2f}%>"
        )


# ============================================================ #
#  MLModel                                                      #
# ============================================================ #

class MLModel(db.Model):
    """Registry of trained machine-learning models."""

    __tablename__ = "ml_models"

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(128), nullable=False)
    target_variable = db.Column(db.String(32), nullable=False)  # metal or index
    model_type = db.Column(db.String(64))   # RandomForestRegressor etc.
    task_type = db.Column(db.String(32))    # regression | classification
    file_path = db.Column(db.String(512))
    feature_names = db.Column(JSONType)
    training_samples = db.Column(db.Integer)
    mae = db.Column(db.Float)
    rmse = db.Column(db.Float)
    r2 = db.Column(db.Float)
    accuracy = db.Column(db.Float)
    precision_score = db.Column(db.Float)
    recall_score = db.Column(db.Float)
    f1_score = db.Column(db.Float)
    training_dataset_description = db.Column(db.Text)
    limitations = db.Column(db.Text)
    trained_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    is_active = db.Column(db.Boolean, default=True)

    predictions = db.relationship(
        "Prediction", backref="ml_model", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return (
            f"<MLModel id={self.id} target={self.target_variable} "
            f"type={self.model_type}>"
        )


# ============================================================ #
#  Prediction                                                   #
# ============================================================ #

class Prediction(db.Model):
    """Output of an ML model prediction for a given sample."""

    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey("samples.id"), nullable=False)
    ml_model_id = db.Column(db.Integer, db.ForeignKey("ml_models.id"), nullable=False)
    predicted_value = db.Column(db.Float)
    predicted_class = db.Column(db.String(64))
    prediction_inputs = db.Column(JSONType)
    uncertainty_lower = db.Column(db.Float)
    uncertainty_upper = db.Column(db.Float)
    predicted_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return f"<Prediction id={self.id} value={self.predicted_value}>"


# ============================================================ #
#  CalculationMethodology                                       #
# ============================================================ #

class CalculationMethodology(db.Model):
    """
    Persists the exact formula parameters used for each index calculation run.
    Provides an audit trail for scientific reproducibility.
    """

    __tablename__ = "calculation_methodologies"

    id = db.Column(db.Integer, primary_key=True)
    index_type = db.Column(db.String(32))
    standard_profile = db.Column(db.String(64))
    formula_description = db.Column(db.Text)
    reference_citations = db.Column(JSONType)
    parameter_snapshot = db.Column(JSONType)  # standard limits used at calc time
    calculated_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    notes = db.Column(db.Text)

    def __repr__(self) -> str:
        return (
            f"<CalculationMethodology index={self.index_type} "
            f"standard={self.standard_profile}>"
        )
