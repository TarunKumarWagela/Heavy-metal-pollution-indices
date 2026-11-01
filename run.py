"""
HMPIAS — Application entry point.

Usage:
    python run.py                    # development server
    flask --app run:app run          # Flask CLI
    gunicorn "run:create_app()"      # production

Environment variables:
    FLASK_ENV   development | production (default: development)
    SECRET_KEY  required for development and production
    DATABASE_URL SQLAlchemy URI (default: sqlite:///hmpias.db)
"""

import os
import sys

# Ensure the project root is on the Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print("  HMPIAS — Heavy Metal Pollution Index Assessment System")
    print(f"  http://{host}:{port}")
    print("=" * 60)
    app.run(
        host=host,
        port=port,
        debug=app.config.get("DEBUG", False),
    )
