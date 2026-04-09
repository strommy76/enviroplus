#!/usr/bin/env python3
"""
Path:        ~/projects/enviroplus/nws_wx.py
Description: Polls NWS API (Patrick SFB / KCOF) every 10 min and writes
             observations to the 'nws_weather' table in enviro.db.
             Runs as a standalone service alongside ambient_wx.py.

Changelog:
  2026-04-08 16:00:00 EDT  Initial implementation.
"""

import json
import logging
import os
import sqlite3
import time
import urllib.error
import urllib.request
from logging.handlers import RotatingFileHandler

# ── Paths / config ─────────────────────────────────────────────────────────────
_BASE       = os.environ.get("BASE_PATH",   "/home/pistrommy/projects/enviroplus")
LOG_PATH    = os.environ.get("LOG_PATH",    os.path.join(_BASE, "enviro.log"))
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(_BASE, "enviro.db"))

POLL_S      = 600  # 10 minutes
NWS_URL     = "https://api.weather.gov/stations/KCOF/observations/latest"
USER_AGENT  = "BSPiLHX-NWS/1.0 (pistrommy@bspilhx)"

# ── Logging ────────────────────────────────────────────────────────────────────
_fmt     = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s",
                             datefmt="%Y-%m-%d %H:%M:%S")
_fh      = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=5)
_fh.setFormatter(_fmt)
_ch      = logging.StreamHandler()
_ch.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_fh, _ch])

# ── SQLite ─────────────────────────────────────────────────────────────────────
_db = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
_db.execute("PRAGMA journal_mode=WAL")
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
        logging.warning("NWS observation has no timestamp, skipping")
        return
    try:
        _db.execute(
            """
            INSERT OR IGNORE INTO nws_weather VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ts,
                d["temp_f"],        d["humidity"],
                d["wind_speed_mph"], d["wind_gust_mph"],
                d["wind_direction"],
                d["barometer_inhg"],
                d["visibility_miles"],
                d["dewpoint_f"],
                d["heat_index_f"],  d["wind_chill_f"],
                d["precip_1h_in"],
                d["cloud_cover"],   d["conditions"],
            ),
        )
        _db.commit()
        temp_s = f"{d['temp_f']:.1f}°F" if d["temp_f"] is not None else "n/a"
        wind_s = f"{d['wind_speed_mph']:.1f}mph" if d["wind_speed_mph"] is not None else "calm"
        logging.info(f"nws_weather row written  ts={ts}  temp={temp_s}  "
                     f"wind={wind_s}  cond={d['conditions']}")
    except Exception as e:
        logging.warning(f"SQLite write failed: {e}")


# ── Main loop ──────────────────────────────────────────────────────────────────
logging.info("nws_wx starting — station KCOF (Patrick SFB)")

while True:
    try:
        _write(_parse(_fetch()))
    except urllib.error.URLError as e:
        logging.warning(f"NWS API fetch failed: {e}")
    except (KeyError, IndexError, ValueError) as e:
        logging.warning(f"Unexpected NWS API response: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    time.sleep(POLL_S)
