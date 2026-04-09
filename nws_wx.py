#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        nws_wx.py
PATH:        ~/projects/enviroplus/nws_wx.py
DESCRIPTION: Polls NWS API (Patrick SFB / KCOF) every 10 min and writes
             observations to the 'nws_weather' table in enviro.db.
             Runs as a standalone service alongside ambient_wx.py.

CHANGELOG:
2026-04-09 14:00      Claude      [Docs] Update file header to Lexx standard
                                      format
2026-04-09 00:00      Claude      [Refactor] Phase 3 refactor: use shared
                                      services library for config, logging, DB
                                      writes, and signal handling. Added
                                      load_env (was missing), moved hardcoded
                                      NWS_URL and USER_AGENT to .env via
                                      require().
2026-04-08 16:00      Bryan       [Feature] Initial implementation.
--------------------------------------------------------------------------------
"""

import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/home/pistrommy/projects")

from shared.config_service import load_env, require
from shared.db_service import connect, write_row
from shared.logging_service import setup_logger
from shared.signal_handler import install_shutdown_handler

# ── Paths / config ─────────────────────────────────────────────────────────────
_BASE       = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH   = os.path.join(_BASE, ".env")
LOG_PATH    = os.path.join(_BASE, "enviro.log")
SQLITE_PATH = os.path.join(_BASE, "enviro.db")

load_env(_ENV_PATH, expect_key="NWS_STATION")

NWS_STATION = require("NWS_STATION")
USER_AGENT  = require("NWS_USER_AGENT")
POLL_S      = int(require("NWS_POLL_S"))

NWS_URL = f"https://api.weather.gov/stations/{NWS_STATION}/observations/latest"

# ── Logging ────────────────────────────────────────────────────────────────────
log = setup_logger("nws_wx", LOG_PATH)

# ── Signal handler ─────────────────────────────────────────────────────────────
is_shutting_down = install_shutdown_handler(logger=log)

# ── SQLite ─────────────────────────────────────────────────────────────────────
_db = connect(SQLITE_PATH)
_db.execute("""
    CREATE TABLE IF NOT EXISTS nws_weather (
        ts              TEXT PRIMARY KEY,
        temp_f          REAL,
        humidity        REAL,
        wind_speed_mph  REAL,
        wind_gust_mph   REAL,
        wind_direction  INTEGER,
        barometer_inhg  REAL,
        visibility_miles REAL,
        dewpoint_f      REAL,
        heat_index_f    REAL,
        wind_chill_f    REAL,
        precip_1h_in    REAL,
        cloud_cover     TEXT,
        conditions      TEXT
    )
""")
_db.commit()


# ── Unit conversions ───────────────────────────────────────────────────────────
def _c_to_f(c):
    return c * 9.0 / 5.0 + 32.0 if c is not None else None

def _kmh_to_mph(kmh):
    return kmh * 0.621371 if kmh is not None else None

def _pa_to_inhg(pa):
    return pa * 0.00029530 if pa is not None else None

def _m_to_miles(m):
    return m / 1609.344 if m is not None else None

def _mm_to_in(mm):
    return mm / 25.4 if mm is not None else None


def _val(obj):
    """Extract 'value' from an NWS property object, returning None if missing."""
    if obj is None:
        return None
    return obj.get("value")


def _fetch():
    req = urllib.request.Request(NWS_URL, headers={"User-Agent": USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    return data["properties"]


def _parse(p):
    """Parse NWS observation properties into a dict of imperial values."""
    ts = p.get("timestamp")  # ISO 8601 UTC string

    # Cloud cover — take the first layer description if available
    cloud_layers = p.get("cloudLayers", [])
    cloud_cover = None
    if cloud_layers:
        # Use the highest coverage layer's amount
        amounts = {"CLR": 0, "FEW": 1, "SCT": 2, "BKN": 3, "OVC": 4}
        best = max(cloud_layers, key=lambda x: amounts.get(x.get("amount", ""), 0))
        amount_map = {
            "CLR": "Clear", "FEW": "Few Clouds", "SCT": "Partly Cloudy",
            "BKN": "Mostly Cloudy", "OVC": "Overcast"
        }
        cloud_cover = amount_map.get(best.get("amount"), best.get("amount"))

    return {
        "ts":               ts,
        "temp_f":           _c_to_f(_val(p.get("temperature"))),
        "humidity":         _val(p.get("relativeHumidity")),
        "wind_speed_mph":   _kmh_to_mph(_val(p.get("windSpeed"))),
        "wind_gust_mph":    _kmh_to_mph(_val(p.get("windGust"))),
        "wind_direction":   _val(p.get("windDirection")),
        "barometer_inhg":   _pa_to_inhg(_val(p.get("barometricPressure"))),
        "visibility_miles": _m_to_miles(_val(p.get("visibility"))),
        "dewpoint_f":       _c_to_f(_val(p.get("dewpoint"))),
        "heat_index_f":     _c_to_f(_val(p.get("heatIndex"))),
        "wind_chill_f":     _c_to_f(_val(p.get("windChill"))),
        "precip_1h_in":     _mm_to_in(_val(p.get("precipitationLastHour"))),
        "cloud_cover":      cloud_cover,
        "conditions":       p.get("textDescription"),
    }


def _write(d):
    ts = d["ts"]
    if ts is None:
        log.warning("NWS observation has no timestamp, skipping")
        return
    if write_row(_db, "nws_weather", d, or_ignore=True):
        temp_s = f"{d['temp_f']:.1f}°F" if d["temp_f"] is not None else "n/a"
        wind_s = f"{d['wind_speed_mph']:.1f}mph" if d["wind_speed_mph"] is not None else "calm"
        log.info("nws_weather row written  ts=%s  temp=%s  wind=%s  cond=%s",
                 ts, temp_s, wind_s, d["conditions"])


# ── Main loop ──────────────────────────────────────────────────────────────────
log.info("nws_wx starting — station %s", NWS_STATION)

while not is_shutting_down():
    try:
        _write(_parse(_fetch()))
    except urllib.error.URLError as e:
        log.warning("NWS API fetch failed: %s", e)
    except (KeyError, IndexError, ValueError) as e:
        log.warning("Unexpected NWS API response: %s", e)
    except Exception as e:
        log.error("Unexpected error: %s", e, exc_info=True)
    time.sleep(POLL_S)

log.info("nws_wx stopped")
