# HMPIAS — Heavy Metal Pollution Index Assessment System

> A production-structured, scientifically documented full-stack web application for assessing heavy-metal contamination in Indian groundwater using pollution indices, machine learning, GIS visualization and downloadable reports.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Scientific Methodology](#2-scientific-methodology)
3. [Features](#3-features)
4. [Technology Stack](#4-technology-stack)
5. [Project Structure](#5-project-structure)
6. [Installation & Setup](#6-installation--setup)
7. [Running the Application](#7-running-the-application)
8. [API Documentation](#8-api-documentation)
9. [Dataset Sources](#9-dataset-sources)
10. [Testing](#10-testing)
11. [Known Limitations](#11-known-limitations)
12. [Next Development Steps](#12-next-development-steps)

---

## 1. Project Overview

HMPIAS provides researchers, water-quality engineers and environmental regulators with a unified platform to:

- **Upload and validate** groundwater sample datasets (CSV/Excel) from CGWB/NWDP
- **Compute scientifically documented indices** — HPI, HEI, and Degree of Contamination — against BIS IS 10500 or WHO GDWQ limits
- **Visualise** contamination geographically on an interactive India map
- **Predict** metal concentrations using Random Forest and Linear Regression models trained on real uploaded data
- **Generate** professional PDF, Excel and CSV reports with full methodology citations
- **Maintain** an audit trail of every calculation (standard version, metals used, exclusions)

> ⚠ **Disclaimer:** All index classifications are literature-based thresholds and do not constitute regulatory determinations. Consult qualified environmental professionals before taking regulatory action.

---

## 2. Scientific Methodology

### 2.1 Heavy Metal Pollution Index (HPI)

**Reference:** Mohan, S.V., Nithila, P., & Reddy, S.J. (1996). *Journal of Environmental Science and Health, Part A*, 31(2), 283–289. https://doi.org/10.1080/10934529609376357

```
Wᵢ  = 1 / Sᵢ                              (unit weight)
Qᵢ  = |Mᵢ - Iᵢ| / |Sᵢ - Iᵢ| × 100        (sub-index)
HPI = Σ(Wᵢ × Qᵢ) / Σ(Wᵢ)                 (aggregated index)

Effective contribution:   ECᵢ = (Wᵢ×Qᵢ) / Σ(Wᵢ)        — sums to HPI
Percentage contribution:  PCᵢ = (Wᵢ×Qᵢ) / Σ(Wᵢ×Qᵢ) × 100 — sums to 100%
```

- `Mᵢ` = measured concentration (mg/L)
- `Sᵢ` = permissible / reference limit (mg/L)
- `Iᵢ` = ideal value (default: 0 for drinking-water metals)
- Critical level: **HPI ≥ 100** (Mohan et al. 1996, literature-based)

### 2.2 Heavy Metal Evaluation Index (HEI)

**Reference:** Edet, A.E., & Offiong, O.E. (2002). *GeoJournal*, 57(4), 295–304. https://doi.org/10.1023/B:GEJO.0000007250.92458.de

```
HEI = Σ (Hcᵢ / Hmacᵢ)
```

Classification: Low (<10), Medium (10–20), High (≥20)

### 2.3 Degree of Contamination (Cd Index)

**Reference:** Backman, B., et al. (1998). *Environmental Geology*, 36(1–2), 55–64. https://doi.org/10.1007/s002540050320

```
CFᵢ      = (C_Aᵢ / C_Nᵢ) - 1
Cd_index = Σ CFᵢ      (signed Backman formulation — can be negative)
```

> **⚠ Notation:** `Cd_index` = contamination index name. `Cd` (the element cadmium) is always referred to explicitly as "cadmium" or stored as `Cd` metal column. These are never confused in code.

### 2.4 Soil/Sediment Indices (Separate Domain)

| Index | Formula | Reference |
|-------|---------|-----------|
| Contamination Factor (CF) | `CFᵢ = Cᵢ / Bᵢ` | Tomlinson et al. (1980) |
| Pollution Load Index (PLI) | `PLI = (∏ CFᵢ)^(1/n)` | Tomlinson et al. (1980) |
| Geo-accumulation Index (Igeo) | `Igeo = log₂(Cₙ / 1.5Bₙ)` | Müller (1969) |

> **Domain note:** CF, PLI, Igeo apply **exclusively** to soil/sediment (mg/kg dry weight). Never applied to drinking-water samples.

### 2.5 Regulatory Standards

| Standard | Version | Use |
|----------|---------|-----|
| BIS IS 10500 | 2012 + Amendment 2019 | Primary Indian drinking-water standard; AL and PL distinguished |
| WHO GDWQ | 4th ed. + addenda (2022) | International guideline values |

---

## 3. Features

| Module | Features |
|--------|----------|
| **Dashboard** | Live stats, state distribution, metal averages, recent uploads, mini map, quick calculator |
| **Dataset Management** | CSV/Excel upload, drag-and-drop, column mapping, BDL detection, negative/missing flagging, duplicate detection, unit scale warning, download history |
| **Validation Engine** | BDL never → zero; negative flagged; coordinates checked; India bbox check; unit mismatch heuristic |
| **Index Calculator** | HPI, HEI, Cd_index (manual entry or from DB); per-metal contribution table; pie chart; classification disclaimer |
| **GIS Analysis** | Leaflet.js India map, metal-specific colour coding vs BIS limits, popup with measurements, state filter |
| **Machine Learning** | RF Regressor + Linear Regression per metal; no target leakage; RF uncertainty (±1.96σ); MAE/RMSE/R² display |
| **Reports** | PDF (ReportLab), Excel (openpyxl), CSV; includes methodology & citations |
| **Standards** | BIS + WHO tables; classification thresholds with source citations |
| **Soil Indices** | Separate `/api/soil/` namespace; CF, PLI, Igeo |

---

## 4. Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.14 |
| Web Framework | Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 + SQLAlchemy 2.0 |
| Migrations | Flask-Migrate 4.1 (Alembic) |
| Data Science | Pandas 3.1, NumPy 2.5, scikit-learn 1.9 |
| ML Storage | joblib 1.6 |
| Reports | ReportLab 5.1, openpyxl 3.1 |
| Database | SQLite (dev) — PostgreSQL-ready |
| Frontend | Bootstrap 5.3, Plotly.js 2.27, Leaflet.js 1.9 |
| Maps | OpenStreetMap tiles |
| Testing | pytest 9.2 |

---

## 5. Project Structure

```
HMPIAS/
├── run.py                          # Application entry point
├── config.py                       # Environment configurations
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── app/                            # Flask application package
│   ├── __init__.py                 # Application factory + DB seeding
│   ├── models.py                   # SQLAlchemy ORM models
│   │
│   ├── routes/                     # Blueprint route handlers
│   │   ├── dashboard.py            # GET / + /api/dashboard/stats
│   │   ├── dataset.py              # /dataset/* endpoints
│   │   ├── calculations.py         # /api/calculate/* endpoints
│   │   ├── predictions.py          # /api/ml, /api/predict, /api/ml/train
│   │   ├── gis.py                  # /api/gis/* endpoints
│   │   ├── reports.py              # /api/export/* endpoints
│   │   ├── standards.py            # /api/standards/* endpoints
│   │   ├── soil.py                 # /api/soil/* endpoints
│   │   └── pages.py                # /gis, /about page routes
│   │
│   ├── services/                   # Business logic layer
│   │   ├── dataset_service.py      # Upload pipeline, CSV ingest
│   │   ├── calculation_service.py  # Orchestrates index calculations
│   │   └── report_service.py       # PDF, Excel, CSV generation
│   │
│   └── templates/                  # Jinja2 HTML templates
│       ├── base.html               # Sidebar layout, topbar, shared CSS/JS
│       ├── dashboard.html          # Main monitoring dashboard
│       ├── dataset.html            # Dataset management
│       ├── calculator.html         # Index calculator
│       ├── prediction.html         # ML training & prediction
│       ├── gis.html                # Full-screen map
│       ├── reports.html            # Report download
│       ├── standards.html          # Standards reference
│       └── about.html              # Project info
│
├── src/                            # Domain/science library (Flask-independent)
│   ├── indices/
│   │   ├── hpi.py                  # HPI engine (Mohan et al. 1996)
│   │   ├── hei.py                  # HEI engine (Edet & Offiong 2002)
│   │   ├── degree_of_contamination.py  # Cd Index (Backman et al. 1998)
│   │   └── soil_indices.py         # CF, PLI, Igeo (soil/sediment only)
│   │
│   ├── validation/
│   │   └── validator.py            # DataFrame validation + BDL parsing
│   │
│   ├── standards/
│   │   └── standards_loader.py     # DB-backed standard profile loader
│   │
│   └── machine_learning/
│       ├── train.py                # RF + LR training pipeline
│       └── predict.py              # Inference + uncertainty estimation
│
├── data/
│   ├── raw/                        # Uploaded original files
│   ├── processed/                  # Processed datasets + reports
│   └── reference/                  # Reference data
│
├── models/                         # Saved ML model files (.joblib)
│
└── tests/
    ├── conftest.py
    ├── test_all.py                 # 52 automated tests (all pass)
    └── verify_live.py              # Live server verification script
```

---

## 6. Installation & Setup

### Prerequisites
- Python 3.14+
- pip

### Create a virtual environment and install dependencies

**Windows (PowerShell):**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure environment variables

Create a local `.env` file from the example. `.env` is ignored by Git; do not
commit it or share its contents.

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

**macOS / Linux:**

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the generated value into the `SECRET_KEY` entry in `.env`. A secret key is
required in development and production; production keys must be at least 32
characters long. For production, also set `FLASK_ENV=production` and configure
a production database with `DATABASE_URL`.

The project targets Python 3.14. `requirements.txt` is the source of truth for
dependency constraints; install and test dependencies in a virtual environment
for your platform.

---

## 7. Running the Application

Run from the project root with the virtual environment activated and `.env`
configured:

```bash
python run.py
```

Open: **http://127.0.0.1:5000**

Override the default host and port with `HOST` and `PORT` in `.env`. The Flask
CLI is also available for development:

```bash
flask --app run:app run --debug
```

For production, use a production WSGI server rather than Flask's development
server. For example, on Linux:

```bash
gunicorn run:app
```

On Windows, the `waitress` package is installed from `requirements.txt`:

```powershell
waitress-serve --call app:create_app
```

### Database migrations (after model changes)

```bash
flask --app run:app db init
flask --app run:app db migrate -m "description"
flask --app run:app db upgrade
```

> The database is created automatically on first run. BIS IS 10500:2012 and WHO GDWQ standards are seeded automatically.

---

## 8. API Documentation

### Health & General

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | System health check |
| `GET` | `/api/standards` | List all standards |
| `GET` | `/api/standards/profiles` | List standard profiles |
| `GET` | `/api/standards/profile/<name>` | Get profile limits |
| `GET` | `/api/dashboard/stats` | Dashboard statistics |

### Dataset

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/dataset/upload` | Upload CSV/Excel (multipart) |
| `GET` | `/dataset/uploads` | List all uploads |
| `GET` | `/dataset/uploads/<id>/samples` | Paginated sample list |
| `GET` | `/dataset/sample-csv` | Download template CSV |
| `DELETE` | `/dataset/uploads/<id>` | Delete upload + samples |

### Groundwater Index Calculations

| Method | Endpoint | Body / Notes |
|--------|----------|-------------|
| `POST` | `/api/calculate/hpi` | `{measurements, standards, ideal_values?, bdl_flags?}` |
| `POST` | `/api/calculate/hei` | `{measurements, standards, bdl_flags?}` |
| `POST` | `/api/calculate/cd` | `{measurements, reference_values, non_negative?}` |
| `POST` | `/api/calculate/all` | All three indices in one call |
| `POST` | `/api/calculate/sample/<id>` | Calculate for DB sample |
| `POST` | `/api/calculate/dataset/<upload_id>` | Calculate for all samples in upload |
| `GET` | `/api/results/<id>` | Retrieve stored result |

### Soil/Sediment Indices (separate namespace)

| Method | Endpoint | Body |
|--------|----------|------|
| `POST` | `/api/soil/calculate/cf` | `{metal, measured, background}` — mg/kg dw |
| `POST` | `/api/soil/calculate/pli` | `{measurements, background_values}` |
| `POST` | `/api/soil/calculate/igeo` | `{metal, measured, background}` |

### Machine Learning

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ml/train` | Train models on uploaded data |
| `GET` | `/api/ml/models` | List trained models |
| `POST` | `/api/predict` | Predict using a saved model |

### Reports & Exports

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/export/csv/<upload_id>` | Download samples as CSV |
| `GET` | `/api/export/excel/<upload_id>` | Download samples + results as Excel |
| `GET` | `/api/export/pdf/<sample_id>` | Download PDF report for one sample |

### GIS

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/gis/samples?metal=Pb&state=Bihar` | GeoJSON FeatureCollection |
| `GET` | `/api/gis/states` | State-wise sample counts |

---

## 9. Dataset Sources

**Primary:** [CGWB / National Water Data Portal](https://nwdp.nwic.gov.in/)

**Supported columns after mapping:**

```
sample_id, state, district, station,
latitude, longitude, sample_date,
pH, EC, TDS,
Fe, As, U, Mn, Cu, Pb, Zn, Ni, Cd, Cr,
fluoride, nitrate
```

All concentrations stored in **mg/L**. µg/L values must be divided by 1000 before upload. The validator provides a heuristic unit-scale warning if values appear out of plausible range.

**BDL entry:** Use `BDL`, `ND`, `<DL`, `Not Detected`, `Trace` — never zero. These are preserved with a `_bdl` flag column and excluded from all calculations.

---

## 10. Testing

### Run all tests

```bash
cd HMPIAS
python -m pytest tests/test_all.py -v
```

**Result: 52 tests, 52 passed (0 failed)**

### Test categories

| Class | Tests | Coverage |
|-------|-------|---------|
| `TestHPI` | 11 | HPI value, contributions, BDL exclusion, negatives, zero-standard |
| `TestHEI` | 4 | HEI value, BDL, negatives, ratios |
| `TestDegreeOfContamination` | 4 | Signed Cd_index, non-negative variant, BDL, CF formula |
| `TestSoilIndices` | 8 | CF, PLI, Igeo calculations and classifications |
| `TestValidation` | 9 | BDL detection, parse, DataFrame validation |
| `TestAPI` | 12 | All major endpoints; bad-request handling |
| `TestDomainSeparation` | 2 | Soil vs groundwater domain isolation |

### Illustrative verification values

| Index | Expected | Verified |
|-------|---------|---------|
| HPI | 84.754902 | ✅ 84.754902 |
| HEI | 2.766667 | ✅ 2.766667 |
| Cd_index | −0.233333 | ✅ −0.233333 |
| Pb % contribution | 39.039908% | ✅ 39.039907% |
| Cd % contribution | 57.836900% | ✅ 57.836900% |
| Cr % contribution | 3.123192% | ✅ 3.123193% |

*(Rounding differences at 6th decimal place.)*

---

## 11. Known Limitations

1. **Authentication not implemented** — MVP only. The schema is forward-compatible; add Flask-Login or OAuth in a later phase.
2. **SQLite** — suitable for development; migrate to PostgreSQL for production multi-user deployments.
3. **ML requires ≥ 30 samples per metal** — models with fewer observations are skipped.
4. **ML spatial generalization** — models are trained on uploaded data only; predictions outside the training region are unreliable.
5. **BIS IS 10500 Amendment 2019** — uranium limits not specified; excluded from BIS calculations.
6. **PDF charts** — the PDF report does not embed Plotly charts (ReportLab only renders tables/text). Excel charts can be added in a later phase.
7. **No rate limiting** — add Flask-Limiter for production deployments.
8. **No input sanitisation for XSS** — implement Content Security Policy headers in production.

---

## 12. Next Development Steps

### Phase 2 (Short-term)
- [ ] User authentication with Flask-Login
- [ ] Role-based access (Admin, Analyst, Viewer)
- [ ] Batch PDF report generation (all samples in one ZIP)
- [ ] Interactive Plotly charts embedded in PDF via image export

### Phase 3 (Medium-term)
- [ ] PostgreSQL migration for production
- [ ] Spatial cross-validation for ML models
- [ ] Real-time CGWB API integration
- [ ] Multi-parameter regression (predict HPI directly)
- [ ] Email-based report delivery

### Phase 4 (Long-term)
- [ ] Docker containerisation
- [ ] REST API versioning (`/api/v1/`)
- [ ] QGIS plugin for direct index calculation
- [ ] Time-series trend analysis across monitoring periods
- [ ] NABL-accredited lab data integration

---

## References

1. Mohan, S.V., Nithila, P., & Reddy, S.J. (1996). Estimation of heavy metals in drinking water and development of heavy metal pollution index. *Journal of Environmental Science and Health, Part A*, 31(2), 283–289.
2. Edet, A.E., & Offiong, O.E. (2002). Evaluation of water quality pollution indices for heavy metal contamination monitoring. *GeoJournal*, 57(4), 295–304.
3. Backman, B., Bodiš, D., Lahermo, P., Rapant, S., & Tarvainen, T. (1998). Application of a groundwater contamination index in Finland and Slovakia. *Environmental Geology*, 36(1–2), 55–64.
4. Tomlinson, D.L., Wilson, J.G., Harris, C.R., & Jeffrey, D.W. (1980). Problems in the assessment of heavy-metal levels in estuaries and the formation of a pollution index. *Helgoländer Meeresuntersuchungen*, 33(1–4), 566–575.
5. Müller, G. (1969). Index of geo-accumulation in sediments of the Rhine River. *GeoJournal*, 2(3), 108–118.
6. Bureau of Indian Standards. IS 10500:2012 (Amendment 2019). Drinking Water — Specification. https://bis.gov.in
7. World Health Organization (2022). *Guidelines for Drinking-water Quality*, 4th ed. incorporating the 1st and 2nd addenda. https://www.who.int/publications/i/item/9789240045064
