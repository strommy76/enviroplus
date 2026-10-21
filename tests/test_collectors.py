"""
--------------------------------------------------------------------------------
FILE:        test_collectors.py
PATH:        ~/projects/enviroplus/tests/test_collectors.py
DESCRIPTION: Ambient and NWS collectors: provider-to-row mappings against
             hand-computed values, response shapes that must be retained as
             malformed rather than lost, and replay rebuilding the derived
             table from retention.

CHANGELOG:
2026-10-11 16:00      Claude      [Feature] Initial tests.
--------------------------------------------------------------------------------
"""

import json
import sqlite3
from datetime import UTC, datetime

import pytest
from shared import raw_retention

import ambient_wx
import nws_wx

MAC = "AA:BB:CC:DD:EE:FF"


def _ambient_body(observation, mac=MAC):
    return json.dumps([{"macAddress": mac, "lastData": observation}]).encode()


# ── Ambient ────────────────────────────────────────────────────────────────────
def test_ambient_row_mapping_hand_values():
    obs = {
        "dateutc": 1_700_000_000_000,
        "tempf": 70.5,
        "dewPoint": 50.1,
        "feelsLike": 69.9,
        "lastRain": "2023-11-14T20:00:00.000Z",
        "winddir": 270,
    }
    row = ambient_wx.row_from_observation(obs)
    # 1,700,000,000 s after the epoch is 2023-11-14 22:13:20 UTC.
    assert row["ts"] == "2023-11-14 22:13:20"
    assert (row["tempf"], row["dewpoint"], row["feelslike"], row["winddir"]) == (
        70.5,
        50.1,
        69.9,
        270,
    )
    assert row["lastrain"] == "2023-11-14T20:00:00.000Z"


@pytest.mark.parametrize(
    "body, outcome",
    [
        (b'{"error": "apiKey invalid"}', raw_retention.OUTCOME_MALFORMED),  # object, not a list
        (b"<html>502</html>", raw_retention.OUTCOME_MALFORMED),
        (b"[]", raw_retention.OUTCOME_EMPTY),
        (
            _ambient_body({"dateutc": 1, "tempf": 1.0}, mac="11:22:33:44:55:66"),
            raw_retention.OUTCOME_EMPTY,
        ),
        (_ambient_body({"tempinf": 70.0}), raw_retention.OUTCOME_EMPTY),  # no dateutc
        (_ambient_body({"dateutc": 1, "tempinf": 70.0}), raw_retention.OUTCOME_PARTIAL),
        (_ambient_body({"dateutc": 1, "tempf": 60.0}), raw_retention.OUTCOME_OK),
    ],
)
def test_ambient_classification_never_raises(body, outcome):
    assert ambient_wx.classify_response(body, MAC.lower())[1] == outcome


def test_ambient_selects_the_configured_station_not_the_first():
    body = json.dumps(
        [
            {"macAddress": "11:22:33:44:55:66", "lastData": {"dateutc": 1, "tempf": 1.0}},
            {"macAddress": MAC, "lastData": {"dateutc": 2, "tempf": 2.0}},
        ]
    ).encode()
    assert ambient_wx.classify_response(body, MAC)[0]["tempf"] == 2.0


def test_ambient_partial_response_is_one_retained_record(monkeypatch, tmp_path):
    raw_retention.configure(tmp_path)
    body = _ambient_body({"dateutc": 1, "tempinf": 70.0})

    class Response:
        def read(self):
            return body

    monkeypatch.setattr(ambient_wx.urllib.request, "urlopen", lambda url, timeout: Response())
    observation = ambient_wx._fetch(
        "https://example.invalid/devices",
        MAC,
        ambient_wx.setup_logger("ambient_test", str(tmp_path / "t.log"), console=False),
    )
    assert observation["tempinf"] == 70.0
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    records = list(raw_retention.read_day("ambient", day))
    assert [outcome for _, outcome, _ in records] == [raw_retention.OUTCOME_PARTIAL]


def test_ambient_replay_rebuilds_rows_from_retention(monkeypatch, tmp_path):
    raw_retention.configure(tmp_path / "raw")
    monkeypatch.setenv("AW_MAC", MAC)
    for ms, temp in ((1_700_000_000_000, 61.0), (1_700_000_060_000, 62.0)):
        raw_retention.retain(
            "ambient",
            _ambient_body({"dateutc": ms, "tempf": temp}),
            outcome=raw_retention.OUTCOME_OK,
        )
    raw_retention.retain("ambient", b"not json", outcome=raw_retention.OUTCOME_MALFORMED)
    db = sqlite3.connect(tmp_path / "rebuilt.db")
    ambient_wx.ensure_schema(db)
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    tally = ambient_wx.replay(db, [day])
    assert tally["written"] == 2 and tally[raw_retention.OUTCOME_MALFORMED] == 1
    rows = db.execute("SELECT ts, tempf, capture_mode FROM outdoor ORDER BY ts").fetchall()
    assert rows == [
        ("2023-11-14 22:13:20", 61.0, "replay"),
        ("2023-11-14 22:14:20", 62.0, "replay"),
    ]


# ── NWS ────────────────────────────────────────────────────────────────────────
def _nws_body(*timestamps, temp_c=0.0):
    return json.dumps(
        {
            "features": [
                {"properties": {"timestamp": ts, "temperature": {"value": temp_c}}}
                for ts in timestamps
            ]
        }
    ).encode()


def test_nws_unit_conversions_hand_values():
    p = {
        "timestamp": "2026-10-11T12:00:00+00:00",
        "temperature": {"value": 100.0},  # 212 F
        "dewpoint": {"value": 0.0},  # 32 F
        "windSpeed": {"value": 10.0},  # 6.21371 mph
        "barometricPressure": {"value": 101_325.0},  # 29.92 inHg
        "visibility": {"value": 1609.344},  # 1 mile
        "precipitationLastHour": {"value": 25.4},  # 1 inch
    }
    row = nws_wx._parse(p, "KMLB")
    assert row["temp_f"] == pytest.approx(212.0)
    assert row["dewpoint_f"] == pytest.approx(32.0)
    assert row["wind_speed_mph"] == pytest.approx(6.21371, abs=1e-5)
    assert row["barometer_inhg"] == pytest.approx(29.92, abs=0.005)
    assert row["visibility_miles"] == pytest.approx(1.0)
    assert row["precip_1h_in"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "body, outcome",
    [
        (b"<html>503</html>", raw_retention.OUTCOME_MALFORMED),
        (b'[{"features": []}]', raw_retention.OUTCOME_MALFORMED),  # list, not an object
        (b'{"status": 503}', raw_retention.OUTCOME_MALFORMED),  # no features
        (b'{"features": [{"properties": {}}]}', raw_retention.OUTCOME_MALFORMED),
        (b'{"features": []}', raw_retention.OUTCOME_EMPTY),
    ],
)
def test_nws_classification_never_raises(body, outcome):
    assert nws_wx.classify_response(body)[1] == outcome


def test_nws_classification_selects_newest():
    newest, outcome, _ = nws_wx.classify_response(
        _nws_body(
            "2026-10-11T10:00:00+00:00", "2026-10-11T12:00:00+00:00", "2026-10-11T11:00:00+00:00"
        )
    )
    assert (
        outcome == raw_retention.OUTCOME_OK and newest["timestamp"] == "2026-10-11T12:00:00+00:00"
    )


def test_nws_replay_writes_fresh_newest_observation(tmp_path):
    raw_retention.configure(tmp_path / "raw")
    raw_retention.retain(
        "nws/KMLB",
        _nws_body(datetime.now(UTC).isoformat(timespec="seconds"), temp_c=20.0),
        outcome=raw_retention.OUTCOME_OK,
    )
    raw_retention.retain(
        "nws/KMLB", _nws_body("2000-01-01T00:00:00+00:00"), outcome=raw_retention.OUTCOME_OK
    )  # stale at capture
    settings = nws_wx.NwsSettings(
        api_base_url="https://api.weather.gov",
        stations=("KMLB",),
        user_agent="t",
        poll_s=600,
        shutdown_check_s=1,
        max_observation_age_s=7200,
        collection_lookback_s=21600,
        sqlite_path=str(tmp_path / "rebuilt.db"),
    )
    db = sqlite3.connect(settings.sqlite_path)
    nws_wx._ensure_schema(db)
    tally = nws_wx.replay(settings, db, [datetime.now(UTC).strftime("%Y-%m-%d")])
    assert tally["written"] == 1 and tally["not_fresh_at_capture"] == 1
    temp, mode = db.execute("SELECT temp_f, capture_mode FROM nws_weather").fetchone()
    assert temp == pytest.approx(68.0) and mode == "replay"  # 20 C = 68 F
