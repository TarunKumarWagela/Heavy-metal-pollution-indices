"""
HMPIAS Automated Test Suite
=============================
Tests covering HPI, HEI, Degree of Contamination, soil indices,
validation engine, API endpoints, and scientific accuracy.

Illustrative test values (from project specification):
  Pb = 0.015 mg/L (measured), Si = 0.010 mg/L
  Cd = 0.002 mg/L (measured), Si = 0.003 mg/L  [Cd = cadmium element]
  Cr = 0.030 mg/L (measured), Si = 0.050 mg/L

Expected results (Ii = 0 for all metals):
  HPI  ≈ 84.754902
  HEI  ≈ 2.766667
  Cd_index ≈ -0.233333  [Cd_index = contamination index, NOT the metal]

  Effective contributions:
    Pb = 33.088235
    Cd = 49.019608  [Cd element contributing to HPI]
    Cr =  2.647059

  Percentage contributions:
    Pb = 39.039908%
    Cd = 57.836900%
    Cr =  3.123192%

These values are illustrative test fixtures, not a regulatory assessment.
"""

import math
import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.indices.hpi import calculate_hpi, hpi_result_to_dict
from src.indices.hei import calculate_hei
from src.indices.degree_of_contamination import calculate_degree_of_contamination
from src.indices.soil_indices import (
    calculate_contamination_factor, calculate_pli, calculate_igeo,
)
from src.validation.validator import (
    validate_dataframe, is_bdl, parse_concentration,
    validate_standards_for_calculation,
)

import pandas as pd


# ============================================================
# Test fixtures
# ============================================================

SITE_A_MEASUREMENTS = {"Pb": 0.015, "Cd": 0.002, "Cr": 0.030}
SITE_A_STANDARDS    = {"Pb": 0.010, "Cd": 0.003, "Cr": 0.050}
SITE_A_IDEAL        = {"Pb": 0.0,   "Cd": 0.0,   "Cr": 0.0}

EXPECTED_HPI              = 84.754902
EXPECTED_HEI              = 2.766667
EXPECTED_CD_INDEX_SIGNED  = -0.233333

EXPECTED_EFFECTIVE = {"Pb": 33.088235, "Cd": 49.019608, "Cr": 2.647059}
EXPECTED_PERCENT   = {"Pb": 39.039908, "Cd": 57.836900, "Cr":  3.123192}

TOLERANCE = 1e-4


# ============================================================
# HPI Tests
# ============================================================

class TestHPI:

    def test_hpi_value_site_a(self):
        """HPI for Site A illustrative values ≈ 84.754902."""
        result = calculate_hpi(
            SITE_A_MEASUREMENTS, SITE_A_STANDARDS, SITE_A_IDEAL
        )
        assert abs(result.hpi - EXPECTED_HPI) < TOLERANCE, (
            f"Expected HPI ≈ {EXPECTED_HPI}, got {result.hpi}"
        )

    def test_hpi_effective_contributions_sum_to_hpi(self):
        """Effective contributions must sum to HPI value."""
        result = calculate_hpi(
            SITE_A_MEASUREMENTS, SITE_A_STANDARDS, SITE_A_IDEAL
        )
        ec_sum = sum(r.effective_contribution for r in result.per_metal)
        assert abs(ec_sum - result.hpi) < TOLERANCE, (
            f"Effective contributions sum {ec_sum} ≠ HPI {result.hpi}"
        )

    def test_hpi_percentage_contributions_sum_to_100(self):
        """Percentage contributions must sum to 100%."""
        result = calculate_hpi(
            SITE_A_MEASUREMENTS, SITE_A_STANDARDS, SITE_A_IDEAL
        )
        pct_sum = sum(r.percentage_contribution for r in result.per_metal)
        assert abs(pct_sum - 100.0) < TOLERANCE, (
            f"% contributions sum {pct_sum} ≠ 100"
        )

    def test_hpi_individual_effective_contributions(self):
        """Verify per-metal effective contributions."""
        result = calculate_hpi(
            SITE_A_MEASUREMENTS, SITE_A_STANDARDS, SITE_A_IDEAL
        )
        pm_dict = {r.metal: r for r in result.per_metal}
        for metal, expected_ec in EXPECTED_EFFECTIVE.items():
            actual = pm_dict[metal].effective_contribution
            assert abs(actual - expected_ec) < TOLERANCE, (
                f"{metal} EC: expected {expected_ec}, got {actual}"
            )

    def test_hpi_individual_percentage_contributions(self):
        """Verify per-metal percentage contributions."""
        result = calculate_hpi(
            SITE_A_MEASUREMENTS, SITE_A_STANDARDS, SITE_A_IDEAL
        )
        pm_dict = {r.metal: r for r in result.per_metal}
        for metal, expected_pct in EXPECTED_PERCENT.items():
            actual = pm_dict[metal].percentage_contribution
            assert abs(actual - expected_pct) < TOLERANCE, (
                f"{metal} %: expected {expected_pct}, got {actual}"
            )

    def test_hpi_classification_site_a(self):
        """Site A HPI < 100 → Low Pollution."""
        result = calculate_hpi(SITE_A_MEASUREMENTS, SITE_A_STANDARDS, SITE_A_IDEAL)
        assert "Low" in result.classification or "Acceptable" in result.classification

    def test_hpi_excludes_negative_concentration(self):
        """Negative concentration must be excluded, not silently used."""
        meas = {"Pb": -0.005, "Cd": 0.002}
        stds = {"Pb": 0.010,  "Cd": 0.003}
        result = calculate_hpi(meas, stds)
        assert "Pb" not in result.metals_used
        assert "Cd" in result.metals_used
        assert "Pb" in result.metals_excluded

    def test_hpi_excludes_bdl_metal(self):
        """BDL metal must be excluded, not set to zero."""
        meas = {"Pb": 0.015, "Cd": 0.002}
        stds = {"Pb": 0.010,  "Cd": 0.003}
        bdl  = {"Cd": True}
        result = calculate_hpi(meas, stds, bdl_flags=bdl)
        assert "Cd" not in result.metals_used
        assert "Pb" in result.metals_used

    def test_hpi_raises_if_no_valid_metals(self):
        """Should raise ValueError if no valid metals remain."""
        with pytest.raises(ValueError):
            calculate_hpi({"Pb": -1.0}, {"Pb": 0.01})

    def test_hpi_raises_if_zero_standard(self):
        """Standard = 0 must not silently produce division by zero."""
        with pytest.raises(ValueError):
            calculate_hpi({"Pb": 0.015}, {"Pb": 0.0})

    def test_hpi_weights_equal_inverse_standard(self):
        """Wi must equal 1/Si."""
        result = calculate_hpi(SITE_A_MEASUREMENTS, SITE_A_STANDARDS)
        for pm in result.per_metal:
            expected_w = 1.0 / pm.reference_limit
            assert abs(pm.weight - expected_w) < 1e-10


# ============================================================
# HEI Tests
# ============================================================

class TestHEI:

    def test_hei_value_site_a(self):
        """HEI for Site A ≈ 2.766667."""
        result = calculate_hei(SITE_A_MEASUREMENTS, SITE_A_STANDARDS)
        assert abs(result.hei - EXPECTED_HEI) < TOLERANCE, (
            f"Expected HEI ≈ {EXPECTED_HEI}, got {result.hei}"
        )

    def test_hei_excludes_bdl(self):
        """BDL metal excluded from HEI."""
        result = calculate_hei(SITE_A_MEASUREMENTS, SITE_A_STANDARDS,
                               bdl_flags={"Pb": True})
        assert "Pb" not in result.metals_used

    def test_hei_negative_excluded(self):
        """Negative concentration excluded from HEI."""
        result = calculate_hei({"Pb": -0.01, "Cd": 0.002}, {"Pb": 0.010, "Cd": 0.003})
        assert "Pb" not in result.metals_used

    def test_hei_ratios_correct(self):
        """Each ratio = Hc/Hmac."""
        result = calculate_hei(SITE_A_MEASUREMENTS, SITE_A_STANDARDS)
        for pm in result.per_metal:
            expected = pm.measured_concentration / pm.max_acceptable_conc
            assert abs(pm.ratio - expected) < 1e-10


# ============================================================
# Degree of Contamination Tests
# ============================================================

class TestDegreeOfContamination:

    def test_cd_index_signed_site_a(self):
        """Signed Cd_index ≈ -0.233333."""
        result = calculate_degree_of_contamination(
            SITE_A_MEASUREMENTS, SITE_A_STANDARDS
        )
        assert abs(result.cd_index - EXPECTED_CD_INDEX_SIGNED) < TOLERANCE, (
            f"Expected Cd_index ≈ {EXPECTED_CD_INDEX_SIGNED}, got {result.cd_index}"
        )

    def test_cd_index_non_negative_variant(self):
        """Non-negative variant CF_i = max(CF_i, 0) gives non-negative result."""
        result = calculate_degree_of_contamination(
            SITE_A_MEASUREMENTS, SITE_A_STANDARDS, non_negative=True
        )
        assert result.cd_index >= 0.0
        assert result.variant == "non_negative"

    def test_cd_index_excludes_bdl(self):
        """BDL excluded from Cd_index."""
        result = calculate_degree_of_contamination(
            SITE_A_MEASUREMENTS, SITE_A_STANDARDS, bdl_flags={"Cr": True}
        )
        assert "Cr" not in result.metals_used

    def test_cf_formula(self):
        """CF_i = (C_A / C_N) - 1."""
        result = calculate_degree_of_contamination(
            SITE_A_MEASUREMENTS, SITE_A_STANDARDS
        )
        pm_dict = {r.metal: r for r in result.per_metal}
        for metal in SITE_A_MEASUREMENTS:
            cf = (SITE_A_MEASUREMENTS[metal] / SITE_A_STANDARDS[metal]) - 1.0
            assert abs(pm_dict[metal].contamination_factor - cf) < 1e-10


# ============================================================
# Soil Indices Tests
# ============================================================

class TestSoilIndices:

    def test_cf_calculation(self):
        """CF = measured / background."""
        r = calculate_contamination_factor(90.0, 30.0, "Pb")
        assert abs(r.cf_value - 3.0) < 1e-10

    def test_cf_classification_low(self):
        assert "Low" in calculate_contamination_factor(15.0, 30.0).classification

    def test_cf_classification_moderate(self):
        assert "Moderate" in calculate_contamination_factor(45.0, 30.0).classification

    def test_cf_classification_considerable(self):
        assert "Considerable" in calculate_contamination_factor(120.0, 30.0).classification

    def test_cf_raises_on_negative_measured(self):
        with pytest.raises(ValueError):
            calculate_contamination_factor(-5.0, 30.0)

    def test_cf_raises_on_zero_background(self):
        with pytest.raises(ValueError):
            calculate_contamination_factor(45.0, 0.0)

    def test_pli_calculation(self):
        """PLI = (CF1 × CF2 × CF3)^(1/3)."""
        meas = {"Pb": 60.0, "Cd": 1.05, "Cr": 210.0}
        bkgd = {"Pb": 20.0, "Cd": 0.35, "Cr": 70.0}
        result = calculate_pli(meas, bkgd)
        # Each CF = 3.0
        expected = 3.0  # (3^3)^(1/3) = 3
        assert abs(result.pli - expected) < TOLERANCE

    def test_igeo_calculation(self):
        """Igeo = log2(C / 1.5B)."""
        r = calculate_igeo(90.0, 30.0, "Pb")
        expected = math.log2(90.0 / (1.5 * 30.0))
        assert abs(r.igeo - expected) < 1e-10

    def test_igeo_uncontaminated(self):
        """C < 1.5B → Igeo ≤ 0 → Class 0."""
        r = calculate_igeo(10.0, 30.0)
        assert r.igeo <= 0
        assert "Class 0" in r.classification


# ============================================================
# Validation Engine Tests
# ============================================================

class TestValidation:

    def _make_df(self, rows):
        return pd.DataFrame(rows)

    def test_bdl_detection_patterns(self):
        """BDL sentinel strings are correctly detected."""
        for val in ["BDL", "bdl", "ND", "N.D.", "<DL", "Not Detected", "BL", "Trace"]:
            assert is_bdl(val), f"Expected {val!r} to be BDL"

    def test_not_bdl(self):
        assert not is_bdl("0.015")
        assert not is_bdl(0.015)
        assert not is_bdl("")
        assert not is_bdl(None)

    def test_parse_concentration_valid(self):
        val, bdl = parse_concentration("0.015")
        assert abs(val - 0.015) < 1e-10
        assert bdl is False

    def test_parse_concentration_bdl(self):
        val, bdl = parse_concentration("BDL")
        assert val is None
        assert bdl is True

    def test_parse_concentration_missing(self):
        val, bdl = parse_concentration(None)
        assert val is None
        assert bdl is False

    def test_validate_dataframe_bdl_not_zero(self):
        """BDL must result in NaN, not 0."""
        df = self._make_df([
            {"sample_id": "S1", "Pb": "BDL", "As": "0.005",
             "state": "Rajasthan", "latitude": 26.0, "longitude": 75.0},
        ])
        result = validate_dataframe(df)
        assert result.bdl_counts.get("Pb", 0) == 1
        row = result.cleaned_df.iloc[0]
        assert pd.isna(row["Pb"]), "BDL Pb should be NaN, not 0"
        assert row["Pb_bdl"] is True or row["Pb_bdl"] == True

    def test_validate_dataframe_negative_flagged(self):
        df = self._make_df([
            {"sample_id": "S1", "Pb": -0.01, "As": "0.005",
             "state": "Bihar", "latitude": 25.0, "longitude": 85.0},
        ])
        result = validate_dataframe(df)
        assert result.negative_counts.get("Pb", 0) == 1
        assert any(e.field == "Pb" and "Negative" in e.issue for e in result.errors)

    def test_validate_duplicate_detection(self):
        df = self._make_df([
            {"sample_id": "GW-001", "Pb": 0.01},
            {"sample_id": "GW-001", "Pb": 0.02},
        ])
        result = validate_dataframe(df)
        assert result.duplicate_rows == 2

    def test_validate_standards_zero_rejected(self):
        issues = validate_standards_for_calculation({"Pb": 0.0, "As": 0.05})
        assert any("Pb" in i and "≤ 0" in i for i in issues)

    def test_validate_standards_none_rejected(self):
        issues = validate_standards_for_calculation({"Pb": None})
        assert any("Pb" in i for i in issues)


# ============================================================
# API Integration Tests
# ============================================================

class TestAPI:

    @pytest.fixture
    def client(self):
        """Create a Flask test client with in-memory DB."""
        from app import create_app
        app = create_app("testing")
        with app.test_client() as c:
            with app.app_context():
                yield c

    def test_health_endpoint(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "ok"
        assert data["app"] == "HMPIAS"

    def test_calculate_hpi_endpoint(self, client):
        r = client.post("/api/calculate/hpi", json={
            "measurements": {"Pb": 0.015, "Cd": 0.002, "Cr": 0.030},
            "standards":    {"Pb": 0.010, "Cd": 0.003, "Cr": 0.050},
        })
        assert r.status_code == 200
        data = r.get_json()
        assert "hpi" in data
        assert abs(data["hpi"] - EXPECTED_HPI) < TOLERANCE

    def test_calculate_hei_endpoint(self, client):
        r = client.post("/api/calculate/hei", json={
            "measurements": SITE_A_MEASUREMENTS,
            "standards":    SITE_A_STANDARDS,
        })
        assert r.status_code == 200
        data = r.get_json()
        assert abs(data["hei"] - EXPECTED_HEI) < TOLERANCE

    def test_calculate_cd_endpoint(self, client):
        r = client.post("/api/calculate/cd", json={
            "measurements":    SITE_A_MEASUREMENTS,
            "reference_values": SITE_A_STANDARDS,
        })
        assert r.status_code == 200
        data = r.get_json()
        assert abs(data["cd_index"] - EXPECTED_CD_INDEX_SIGNED) < TOLERANCE

    def test_calculate_all_endpoint(self, client):
        r = client.post("/api/calculate/all", json={
            "measurements": SITE_A_MEASUREMENTS,
            "standards":    SITE_A_STANDARDS,
        })
        assert r.status_code == 200
        data = r.get_json()
        assert "HPI" in data and "HEI" in data and "Cd_index" in data

    def test_standards_list_endpoint(self, client):
        r = client.get("/api/standards")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_soil_cf_endpoint(self, client):
        r = client.post("/api/soil/calculate/cf", json={
            "metal": "Pb", "measured": 60.0, "background": 20.0,
        })
        assert r.status_code == 200
        data = r.get_json()
        assert abs(data["contamination_factor_CF"] - 3.0) < TOLERANCE

    def test_soil_pli_endpoint(self, client):
        r = client.post("/api/soil/calculate/pli", json={
            "measurements": {"Pb": 60.0, "Cd": 1.05, "Cr": 210.0},
            "background_values": {"Pb": 20.0, "Cd": 0.35, "Cr": 70.0},
        })
        assert r.status_code == 200
        data = r.get_json()
        assert abs(data["pli"] - 3.0) < TOLERANCE

    def test_soil_igeo_endpoint(self, client):
        r = client.post("/api/soil/calculate/igeo", json={
            "metal": "Pb", "measured": 90.0, "background": 30.0,
        })
        assert r.status_code == 200

    def test_hpi_bad_request_no_measurements(self, client):
        r = client.post("/api/calculate/hpi", json={"standards": {"Pb": 0.01}})
        assert r.status_code in (400, 422)

    def test_dashboard_stats(self, client):
        r = client.get("/api/dashboard/stats")
        assert r.status_code == 200

    def test_gis_samples(self, client):
        r = client.get("/api/gis/samples")
        assert r.status_code == 200
        data = r.get_json()
        assert data["type"] == "FeatureCollection"


# ============================================================
# Soil vs Groundwater separation test
# ============================================================

class TestDomainSeparation:

    def test_soil_igeo_returns_domain_field(self):
        """Soil endpoints must return a domain='soil_sediment' field."""
        from app import create_app
        app = create_app("testing")
        with app.test_client() as c:
            with app.app_context():
                r = c.post("/api/soil/calculate/igeo",
                           json={"metal":"Pb","measured":90.0,"background":30.0})
                data = r.get_json()
                assert data.get("domain") == "soil_sediment"

    def test_groundwater_hpi_has_no_domain_field(self):
        """Groundwater HPI endpoint must NOT return domain='soil_sediment'."""
        from app import create_app
        app = create_app("testing")
        with app.test_client() as c:
            with app.app_context():
                r = c.post("/api/calculate/hpi",
                           json={"measurements":{"Pb":0.015},"standards":{"Pb":0.01}})
                data = r.get_json()
                assert data.get("domain") != "soil_sediment"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
