"""
--------------------------------------------------------------------------------
FILE:        test_screens.py
PATH:        ~/projects/enviroplus/tests/test_screens.py
DESCRIPTION: AQI against hand-computed EPA values, and every display page
             rendered with full and with absent data.

CHANGELOG:
2026-10-11 15:10      Claude      [Feature] Initial tests for enviro_screens.
--------------------------------------------------------------------------------
"""

import json
from pathlib import Path

import pytest

import enviro_screens as screens

THRESHOLDS = {
    "temp_f": {"green_min": 65, "green_max": 80, "yellow_min": 55, "yellow_max": 90},
    "humidity": {"green_min": 30, "green_max": 70, "yellow_min": 20, "yellow_max": 80},
    "oxidising_k": {"green_max": 40, "yellow_max": 60},
    "reducing_k": {"yellow_min": 60, "green_min": 90},
    "ammonia_k": {"yellow_min": 80, "green_min": 140},
    "co2_ppm": {"green_min": 0, "green_max": 1000, "yellow_min": 0, "yellow_max": 2000},
}


# Expected values worked by hand from the 2024 EPA PM2.5 table:
# AQI = (I_hi - I_lo) / (C_hi - C_lo) * (C - C_lo) + I_lo, after truncating C.
@pytest.mark.parametrize(
    "pm25, expected",
    [
        (0.0, 0),
        (9.0, 50),  # top of Good under the 2024 table (was 12.0)
        (9.05, 50),  # truncates to 9.0
        (9.1, 51),
        (12.0, 56),  # 49/26.3 * 2.9 + 51 = 56.4: Moderate, not the old Good 50
        (35.4, 100),
        (55.5, 151),
        (125.4, 200),  # top of Unhealthy under the 2024 table (was 150.4)
        (225.5, 301),
    ],
)
def test_pm25_aqi_matches_2024_epa_table(pm25, expected):
    assert screens.pm_aqi(pm25, None) == expected


# PM10 table (unchanged by the 2024 rule), truncated to whole ug/m3.
@pytest.mark.parametrize(
    "pm10, expected", [(54, 50), (55, 51), (154.9, 100), (425, 301), (604, 500)]
)
def test_pm10_aqi_matches_epa_table(pm10, expected):
    assert screens.pm_aqi(None, pm10) == expected


def test_aqi_is_the_larger_sub_index():
    # PM10 155 is the bottom of its USG band (101); PM2.5 5.0 alone is 28.
    assert screens.pm_aqi(5.0, 155) == 101


def test_absent_pm_is_no_aqi_not_zero():
    assert screens.pm_aqi(None, None) is None
    assert screens.aqi_category(None) == ("NO DATA", screens.DIM)


@pytest.mark.parametrize(
    "aqi, name",
    [
        (50, "GOOD"),
        (51, "MODERATE"),
        (100, "MODERATE"),
        (101, "SENSITIVE"),
        (150, "SENSITIVE"),
        (151, "UNHEALTHY"),
        (200, "UNHEALTHY"),
        (201, "V UNHEALTHY"),
        (300, "V UNHEALTHY"),
        (301, "HAZARDOUS"),
    ],
)
def test_category_edges(aqi, name):
    assert screens.aqi_category(aqi)[0] == name


def _state(present):
    v = (lambda x: x) if present else (lambda x: None)
    pm = {"pm1": v(1.0), "pm25": v(2.0), "pm10": v(3.0)}
    gas = {"oxidising": 40.0, "reducing": 100.0, "ammonia": 150.0}
    return {
        "indoor": {"temp_f": v(72.0), "humidity": v(45.0), "pressure": 1013.0},
        "pm": pm,
        "pm_hist": {k: [v(1.0), v(2.0), None, value] for k, value in pm.items()},
        "gas": gas,
        "gas_hist": {k: [value] * 4 for k, value in gas.items()},
        "co2": v(612.0),
        "co2_hist": [v(600.0), None, v(640.0)],
        "outdoor": {
            "tempf": 68.0,
            "humidity": 60.0,
            "windspeedmph": 4.0,
            "windgustmph": 9.0,
            "winddir": 270,
            "uv": 3,
            "dailyrainin": 0.1,
        }
        if present
        else None,
        "outdoor_temp_hist": [v(66.0), v(67.0), None, v(68.0)],
        "wind_hist": [v(2.0), v(3.0), None, v(4.0)],
        "thresholds": THRESHOLDS,
    }


@pytest.mark.parametrize("present", [True, False])
@pytest.mark.parametrize("page", range(len(screens.PAGES)))
def test_every_page_renders_full_and_cabled_dropout_data(page, present):
    img = screens.render(page, _state(present))
    assert img.size == (screens.W, screens.H)


def test_pages_render_distinct_content():
    frames = [screens.render(p, _state(True)).tobytes() for p in range(len(screens.PAGES))]
    assert len(set(frames)) == len(frames)


@pytest.mark.parametrize(
    "kohm, color", [(90.0, screens.GREEN), (50.0, screens.YELLOW), (30.0, screens.RED)]
)
def test_oxidising_bands_keep_the_calibrated_direction(kohm, color):
    # Operator-calibrated bands (2026-03-16): the indoor baseline, about 90 kOhm,
    # is green; resistance at or below oxidising_k.green_max is red.
    assert screens.gas_color("oxidising", kohm, THRESHOLDS) == color


# Edges from the committed dashboard config, not a copy, so the test sees the
# values the device runs with.
CO2_BAND = json.loads(
    (Path(__file__).resolve().parents[1] / "dynamic_config.pi5.json").read_text()
)["thresholds"]["co2_ppm"]


@pytest.mark.parametrize(
    "ppm, color",
    [
        (1000.0, screens.GREEN),
        (1001.0, screens.YELLOW),
        (2000.0, screens.YELLOW),
        (2001.0, screens.ORANGE),
        (None, screens.DIM),
    ],
)
def test_co2_band_follows_the_uba_guide_values(ppm, color):
    assert screens.band_color(ppm, CO2_BAND) == color


def test_co2_presence_changes_rendered_content():
    with_co2, without = _state(True), _state(True)
    without["co2"] = None
    without["co2_hist"] = [None] * len(without["co2_hist"])
    without["indoor"]["humidity"] = None
    page = screens.PAGES.index(screens._co2)
    assert screens.render(page, with_co2).tobytes() != screens.render(page, without).tobytes()
