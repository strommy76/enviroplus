#!/usr/bin/env python3
"""
Path:        ~/projects/enviroplus/airnow_wx.py
Description: Polls AirNow (EPA) API every 30 min and writes air quality
             observations to the 'epa_air_quality' table in enviro.db.
             Runs as a standalone service alongside ambient_wx.py.

Changelog:
  2026-04-08 20:00:00 EDT  Initial implementation.
"""

import json
import logging
import os
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

load_dotenv()

# ── Paths / config ─────────────────────────────────────────────────────────────
_BASE       = os.environ.get("BASE_PATH",   "/home/pistrommy/projects/enviroplus")
LOG_PATH    = os.environ.get("LOG_PATH",    os.path.join(_BASE, "enviro.log"))
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(_BASE, "enviro.db"))

AIRNOW_KEY  = os.environ["AIRNOW_API_KEY"]
POLL_S      = 1800  # 30 minutes
LAT         = 28.1761
LON         = -80.5901
DISTANCE    = 50

AIRNOW_URL = (
    f"https://www.airnowapi.org/aq/observation/latLong/current/"
    f"?format=application/json&latitude={LAT}&longitude={LON}"
    f"&distance={DISTANCE}&API_KEY={AIRNOW_KEY}"
)

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
    CREATE TABLE IF NOT EXISTS epa_air_quality (
        ts              TEXT PRIMARY KEY,
        pm25_aqi        INTEGER,
        pm25_category   TEXT,
        pm10_aqi        INTEGER,
        pm10_category   TEXT,
        ozone_aqi       INTEGER,
        ozone_category  TEXT,
        reporting_area  TEXT
    )
""")
_db.commit()


def _fetch():
    req = urllib.request.Request(AIRNOW_URL)
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    return data


def _parse(observations):
    """Parse AirNow observation list into a flat dict."""
    if not observations:
        return None

    # Build a lookup by parameter name
    by_param = {}
    for obs in observations:
        by_param[obs.get("ParameterName", "")] = obs

    # Use the first observation's DateObserved + HourObserved to build ts
    first = observations[0]
    date_str = first.get("DateObserved", "").strip()
    hour = first.get("HourObserved", 0)
    # DateObserved is "YYYY-MM-DD", HourObserved is integer 0-23
    ts = f"{date_str} {hour:02d}:00:00"

    reporting_area = first.get("ReportingArea", "")

    pm25 = by_param.get("PM2.5", {})
    pm10 = by_param.get("PM10", {})
    ozone = by_param.get("O3", {})

    return {
        "ts":              ts,
        "pm25_aqi":        pm25.get("AQI"),
        "pm25_category":   pm25.get("Category", {}).get("Name") if isinstance(pm25.get("Category"), dict) else pm25.get("Category"),
        "pm10_aqi":        pm10.get("AQI"),
        "pm10_category":   pm10.get("Category", {}).get("Name") if isinstance(pm10.get("Category"), dict) else pm10.get("Category"),
        "ozone_aqi":       ozone.get("AQI"),
        "ozone_category":  ozone.get("Category", {}).get("Name") if isinstance(ozone.get("Category"), dict) else ozone.get("Category"),
        "reporting_area":  reporting_area,
    }


def _write(d):
    if d is None:
        logging.warning("AirNow returned no observations, skipping")
        return
    ts = d["ts"]
    try:
        _db.execute(
            """
            INSERT OR IGNORE INTO epa_air_quality VALUES
            (?,?,?,?,?,?,?,?)
            """,
            (
                ts,
                d["pm25_aqi"],     d["pm25_category"],
                d["pm10_aqi"],     d["pm10_category"],
                d["ozone_aqi"],    d["ozone_category"],
                d["reporting_area"],
            ),
        )
        _db.commit()
        pm25_s = str(d["pm25_aqi"]) if d["pm25_aqi"] is not None else "n/a"
        o3_s = str(d["ozone_aqi"]) if d["ozone_aqi"] is not None else "n/a"
        logging.info(f"epa_air_quality row written  ts={ts}  PM2.5={pm25_s}  "
                     f"O3={o3_s}  area={d['reporting_area']}")
    except Exception as e:
        logging.warning(f"SQLite write failed: {e}")


# ── Main loop ──────────────────────────────────────────────────────────────────
logging.info("airnow_wx starting — Melbourne, FL reporting area")

while True:
    try:
        _write(_parse(_fetch()))
    except urllib.error.URLError as e:
        logging.warning(f"AirNow API fetch failed: {e}")
    except (KeyError, IndexError, ValueError) as e:
        logging.warning(f"Unexpected AirNow API response: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    time.sleep(POLL_S)
