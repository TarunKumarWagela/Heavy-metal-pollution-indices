"""
HMPIAS — Flask Application Factory
====================================
Creates and configures the Flask application.

Blueprints registered here:
  * dashboard   — main landing page
  * dataset_bp  — upload, preview, validate
  * calc_bp     — index calculations (HPI, HEI, Cd)
  * pred_bp     — machine-learning predictions
  * gis_bp      — GIS data endpoints
  * reports_bp  — PDF / Excel / CSV downloads
  * standards_bp— standards management
  * soil_bp     — soil/sediment index APIs (separate namespace)

Authentication is intentionally excluded from MVP.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, jsonify
from flask_migrate import Migrate

from app.models import db
from config import ProductionConfig, get_config

migrate = Migrate()
logger = logging.getLogger(__name__)


def create_app(env: str | None = None) -> Flask:
    """Application factory."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    cfg = get_config(env)
    app.config.from_object(cfg)

    secret_key = app.config.get("SECRET_KEY")
    placeholder_keys = {
        "change-me-in-prod",
        "change-me-in-production",
        "dev-fallback-key-must-be-set-in-env",
        "replace-with-a-random-secure-secret-key",
    }
    if not app.config.get("TESTING") and (
        not secret_key
        or not secret_key.strip()
        or secret_key.strip().lower() in placeholder_keys
    ):
        raise ValueError(
            "A valid SECRET_KEY must be set in the .env file or environment."
        )
    if cfg is ProductionConfig and secret_key and len(secret_key.strip()) < 32:
        raise ValueError(
            "Production SECRET_KEY must contain at least 32 characters."
        )

    # Ensure required directories exist
    for folder_key in ("UPLOAD_FOLDER", "PROCESSED_FOLDER", "MODEL_FOLDER", "REPORT_FOLDER"):
        folder = app.config.get(folder_key)
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Extensions
    # ------------------------------------------------------------------ #
    db.init_app(app)
    migrate.init_app(app, db)

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    # ------------------------------------------------------------------ #
    # Blueprints
    # ------------------------------------------------------------------ #
    from app.routes.dashboard import dashboard_bp
    from app.routes.dataset import dataset_bp
    from app.routes.calculations import calc_bp
    from app.routes.predictions import pred_bp
    from app.routes.gis import gis_bp
    from app.routes.reports import reports_bp
    from app.routes.standards import standards_bp
    from app.routes.soil import soil_bp
    from app.routes.pages import pages_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(dataset_bp, url_prefix="/dataset")
    app.register_blueprint(calc_bp, url_prefix="/api")
    app.register_blueprint(pred_bp, url_prefix="/api")
    app.register_blueprint(gis_bp, url_prefix="/api/gis")
    app.register_blueprint(reports_bp, url_prefix="/api")
    app.register_blueprint(standards_bp, url_prefix="/api")
    app.register_blueprint(soil_bp, url_prefix="/api/soil")
    app.register_blueprint(pages_bp)

    # ------------------------------------------------------------------ #
    # Security Headers
    # ------------------------------------------------------------------ #
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # ------------------------------------------------------------------ #
    # Health check
    # ------------------------------------------------------------------ #
    @app.get("/api/health")
    def health():  # type: ignore[return-value]
        return jsonify({"status": "ok", "version": "1.0.0", "app": "HMPIAS"})

    # ------------------------------------------------------------------ #
    # Global error handlers
    # ------------------------------------------------------------------ #
    @app.errorhandler(404)
    def not_found(e):  # type: ignore[return-value]
        return jsonify({"error": "Not found", "status": 404}), 404

    @app.errorhandler(400)
    def bad_request(e):  # type: ignore[return-value]
        return jsonify({"error": str(e), "status": 400}), 400

    @app.errorhandler(500)
    def internal_error(e):  # type: ignore[return-value]
        logger.exception("Unhandled server error")
        return jsonify({"error": "Internal server error", "status": 500}), 500

    # ------------------------------------------------------------------ #
    # Database initialisation
    # ------------------------------------------------------------------ #
    with app.app_context():
        db.create_all()
        _seed_standards(app)

    logger.info("HMPIAS application created successfully (env=%s)", env or "development")
    return app


def _seed_standards(app: Flask) -> None:
    """
    Seed the database with regulatory standards on first run.

    Sources:
      * BIS IS 10500:2012 (Bureau of Indian Standards — Drinking Water Specification)
        Amendment 1 (2019) — https://bis.gov.in
      * WHO Guidelines for Drinking-water Quality, 4th edition incorporating the
        1st and 2nd addenda (2022) — https://www.who.int/publications/i/item/9789240045064

    IMPORTANT: Values are taken from the official documents.
    Acceptable limits (AL) and Permissible Limits (PL) follow BIS IS 10500 terminology.
    WHO uses a single Guideline Value (GV). Do not conflate them.
    All values stored in mg/L.
    """
    from app.models import WaterStandard

    # Check if already seeded
    if WaterStandard.query.first():
        # If Uranium BIS standard is missing (bug fix: it was previously skipped),
        # seed it now without re-seeding everything.
        u_bis = WaterStandard.query.filter_by(
            standard_name="BIS IS 10500", metal="U"
        ).first()
        if not u_bis:
            logger.info("Patching missing Uranium BIS IS 10500 standard …")
            db.session.add(WaterStandard(
                standard_name="BIS IS 10500",
                version="2012 (Amendment 2019)",
                metal="U",
                parameter="Uranium",
                chemical_species="total",
                acceptable_limit=0.015,
                permissible_limit=0.03,
                unit="mg/L",
                source_url="https://bis.gov.in/product/detail/?id=NTUzOA==",
                effective_date="2012-01-01",
                notes="BIS IS 10500 does not specify a limit; provisional: WHO GV 0.03 mg/L adopted as permissible",
            ))
            try:
                db.session.commit()
                logger.info("Uranium BIS standard patched successfully.")
            except Exception:
                db.session.rollback()
                logger.exception("Failed to patch Uranium standard.")
        return

    logger.info("Seeding water quality standards …")
    # ------------------------------------------------------------------
    # BIS IS 10500:2012 (with 2019 amendment) — Drinking Water
    # Reference: Bureau of Indian Standards, IS 10500:2012
    # AL = Acceptable Limit, PL = Permissible Limit
    # ------------------------------------------------------------------
    bis_standards = [
        # (metal, parameter, AL, PL, notes)
        ("Fe",  "Iron",        0.3,    None,   "Total iron; no PL specified — AL is the limit"),
        ("As",  "Arsenic",     0.01,   0.05,   "Total arsenic"),
        ("Mn",  "Manganese",   0.1,    0.3,    "Total manganese"),
        ("Cu",  "Copper",      0.05,   1.5,    "Total copper"),
        ("Pb",  "Lead",        0.01,   0.05,   "Total lead; AL per BIS 2012/2019"),
        ("Zn",  "Zinc",        5.0,    15.0,   "Total zinc"),
        ("Ni",  "Nickel",      0.02,   None,   "Total nickel; no PL specified"),
        ("Cd",  "Cadmium",     0.003,  None,   "Total cadmium; no PL specified"),
        ("Cr",  "Chromium",    0.05,   None,   "Total chromium; Cr(VI) limit"),
        ("F",   "Fluoride",    1.0,    1.5,    "Fluoride"),
        ("NO3", "Nitrate",     45.0,   None,   "Nitrate as NO3"),
        ("U",   "Uranium",     0.015,  0.03,   "BIS IS 10500 does not specify a limit; provisional: WHO GV 0.03 mg/L adopted as permissible"),
    ]

    for metal, param, al, pl, notes in bis_standards:
        if al is None and pl is None:
            continue  # skip metals with no limit defined in the standard
        s = WaterStandard(
            standard_name="BIS IS 10500",
            version="2012 (Amendment 2019)",
            metal=metal,
            parameter=param,
            chemical_species="total",
            acceptable_limit=al,
            permissible_limit=pl,
            unit="mg/L",
            source_url="https://bis.gov.in/product/detail/?id=NTUzOA==",
            effective_date="2012-01-01",
            notes=notes,
        )
        db.session.add(s)

    # ------------------------------------------------------------------
    # WHO Guidelines for Drinking-water Quality, 4th ed. + addenda (2022)
    # GV = Guideline Value (stored in guideline_value column)
    # ------------------------------------------------------------------
    who_standards = [
        # (metal, parameter, GV, chemical_species, notes)
        ("Fe",  "Iron",        None,   "total",    "No health-based GV; aesthetic guideline 0.3 mg/L"),
        ("As",  "Arsenic",     0.01,   "total",    "WHO GV 0.01 mg/L"),
        ("Mn",  "Manganese",   0.08,   "total",    "WHO health-based GV 0.08 mg/L (2022 addenda)"),
        ("Cu",  "Copper",      2.0,    "total",    "WHO GV 2.0 mg/L"),
        ("Pb",  "Lead",        0.01,   "total",    "WHO GV 0.01 mg/L"),
        ("Zn",  "Zinc",        None,   "total",    "No health-based GV; aesthetic"),
        ("Ni",  "Nickel",      0.07,   "total",    "WHO GV 0.07 mg/L"),
        ("Cd",  "Cadmium",     0.003,  "total",    "WHO GV 0.003 mg/L"),
        ("Cr",  "Chromium",    0.05,   "Cr(VI)",   "WHO GV for Cr(VI) 0.05 mg/L"),
        ("F",   "Fluoride",    1.5,    "total",    "WHO GV 1.5 mg/L"),
        ("NO3", "Nitrate",     50.0,   "total",    "WHO GV 50 mg/L as NO3"),
        ("U",   "Uranium",     0.03,   "total",    "WHO GV 0.03 mg/L (provisional)"),
    ]

    for metal, param, gv, species, notes in who_standards:
        if gv is None:
            continue
        s = WaterStandard(
            standard_name="WHO GDWQ",
            version="4th ed. + addenda (2022)",
            metal=metal,
            parameter=param,
            chemical_species=species,
            acceptable_limit=None,
            permissible_limit=None,
            guideline_value=gv,
            unit="mg/L",
            source_url=(
                "https://www.who.int/publications/i/item/9789240045064"
            ),
            effective_date="2022-01-01",
            notes=notes,
        )
        db.session.add(s)

    try:
        db.session.commit()
        logger.info("Water quality standards seeded successfully.")
    except Exception:
        db.session.rollback()
        logger.exception("Failed to seed standards — will retry on next start.")
