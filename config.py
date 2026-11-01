"""
HMPIAS — Heavy Metal Pollution Index Assessment System
Configuration module.

All environment-specific settings are centralised here.
Authentication is intentionally excluded from MVP; the architecture
supports adding it in a later phase without structural changes.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Automatically load environment variables from .env file if present
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration shared by all environments."""

    # ------------------------------------------------------------------ #
    # Flask core
    # ------------------------------------------------------------------ #
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DEBUG = False
    TESTING = False

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'hmpias.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # ------------------------------------------------------------------ #
    # File upload
    # ------------------------------------------------------------------ #
    UPLOAD_FOLDER = str(BASE_DIR / "data" / "raw")
    PROCESSED_FOLDER = str(BASE_DIR / "data" / "processed")
    REFERENCE_FOLDER = str(BASE_DIR / "data" / "reference")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH_MB", 32)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

    # ------------------------------------------------------------------ #
    # ML models
    # ------------------------------------------------------------------ #
    MODEL_FOLDER = str(BASE_DIR / "models")

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #
    REPORT_FOLDER = str(BASE_DIR / "data" / "processed" / "reports")

    # ------------------------------------------------------------------ #
    # Pagination
    # ------------------------------------------------------------------ #
    ITEMS_PER_PAGE = 50

    # ------------------------------------------------------------------ #
    # Scientific constants
    # ------------------------------------------------------------------ #
    # BDL (Below Detection Limit) sentinel string patterns
    BDL_PATTERNS = {"bdl", "bl", "<dl", "nd", "n.d.", "<", "not detected", "bdl"}

    # Unit conversion: µg/L → mg/L factor
    UG_TO_MG = 1e-3


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str | None = None) -> type[Config]:
    env = env or os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
