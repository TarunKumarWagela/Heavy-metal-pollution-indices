# tests package
import pytest

from src.indices.hpi import calculate_hpi


def test_hpi_sample_data():
    concentrations = {
        "Pb": 0.015,
        "Cd": 0.002,
        "Cr": 0.030
    }

    standards = {
        "Pb": 0.010,
        "Cd": 0.003,
        "Cr": 0.050
    }

    result = calculate_hpi(concentrations, standards)

    assert result == pytest.approx(84.7549, abs=0.0001)


def test_hpi_zero_concentrations():
    concentrations = {
        "Pb": 0.0,
        "Cd": 0.0,
        "Cr": 0.0
    }

    standards = {
        "Pb": 0.010,
        "Cd": 0.003,
        "Cr": 0.050
    }

    result = calculate_hpi(concentrations, standards)

    assert result == pytest.approx(0.0)


def test_hpi_rejects_negative_values():
    concentrations = {
        "Pb": -0.015,
        "Cd": 0.002,
        "Cr": 0.030
    }

    standards = {
        "Pb": 0.010,
        "Cd": 0.003,
        "Cr": 0.050
    }

    with pytest.raises(ValueError):
        calculate_hpi(concentrations, standards)