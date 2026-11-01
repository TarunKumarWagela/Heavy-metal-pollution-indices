"""Additional page routes — GIS page, About."""

from flask import Blueprint, render_template
pages_bp = Blueprint("pages", __name__)

@pages_bp.get("/gis")
def gis_page():
    return render_template("gis.html")

@pages_bp.get("/about")
def about_page():
    return render_template("about.html")
