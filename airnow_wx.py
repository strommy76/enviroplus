#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        airnow_wx.py
PATH:        ~/projects/enviroplus/airnow_wx.py
DESCRIPTION: Polls AirNow (EPA) API every 30 min and writes air quality
             observations to the 'epa_air_quality' table in enviro.db.
             Runs as a standalone service alongside ambient_wx.py.

CHANGELOG:
2026-04-09 14:00      Claude      [Docs] Update file header to Lexx standard
                                      format
2026-04-09 00:00      Claude      [Refactor] Phase 3 refactor: use shared
                                      services library for config, logging, DB
                                      writes, and signal handling. Moved
                                      hardcoded LAT/LON/DISTANCE to .env via
                                      require().
2026-04-08 20:00      Bryan       [Feature] Initial implementation.
--------------------------------------------------------------------------------
"""

import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, "/home/pistrommy/projects")

from shared.config_service import load_env, require
from shared.db_service import connect, write_row
from shared.logging_service import setup_logger
from shared.raw_retention import (
    OUTCOME_EMPTY,
    OUTCOME_FETCH_ERROR,
    OUTCOME_MALFORMED,
    OUTCOME_OK,
    OUTCOME_WRITE_ERROR,
    record_outcome,
    retain,
)
from shared.signal_handler import install_shutdown_handler

PROVIDER = "airnow"

# ── Paths / config ─────────────────────────────────────────────────────────────
_BASE       = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH   = os.path.join(_BASE, ".env")
LOG_PATH    = os.path.join(_BASE, "enviro.log")
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(_BASE, "enviro.db"))

load_env(_ENV_PATH, expect_key="AIRNOW_API_KEY")

AIRNOW_KEY  = require("AIRNOW_API_KEY")
LAT         = require("AIRNOW_LAT")
LON         = require("AIRNOW_LON")
DISTANCE    = require("AIRNOW_DISTANCE")
POLL_S      = int(require("AIRNOW_POLL_S"))

AIRNOW_URL = (
    f"https://www.airnowapi.org/aq/observation/latLong/current/"
    f"?format=application/json&latitude={LAT}&longitude={LON}"
    f"&distance={DISTANCE}&API_KEY={AIRNOW_KEY}"
)

# ── Logging ────────────────────────────────────────────────────────────────────
log = setup_logger("airnow_wx", LOG_PATH)

# ── Signal handler ─────────────────────────────────────────────────────────────
is_shutting_down = install_shutdown_handler(logger=log)

# ── SQLite ─────────────────────────────────────────────────────────────────────
_db = connect(SQLITE_PATH)
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


def classify_response(raw: bytes):
    """Decide what arrived, without doing any I/O.

    Returns (observations_or_None, outcome, detail). Pure so the labelling of
    each attempt is testable -- that wiring was previously unreachable by any
    test, and it is where the outcome-misattribution defect lived.
    """
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return None, OUTCOME_MALFORMED, str(exc)
    if not data:
        return data, OUTCOME_EMPTY, "AirNow returned no observations"
    return data, OUTCOME_OK, None


def outcome_for_exception(exc: BaseException) -> str:
    """Map a raised failure to the cause it actually represents.

    A failed derived write is not a failed fetch; recording it as one would
    make the canonical store lie about which subsystem broke.
    """
    if isinstance(exc, sqlite3.Error):
        return OUTCOME_WRITE_ERROR
    return OUTCOME_FETCH_ERROR


def _fetch():
    """Fetch, retain the bytes as received, then parse.

    Retention precedes parsing so the canonical record is the provider's
    response rather than this collector's reading of it. A retention failure is
    logged loudly but does not suppress the derived write.
    """
    req = urllib.request.Request(AIRNOW_URL)
    resp = urllib.request.urlopen(req, timeout=15)
    raw = resp.read()

    data, outcome, detail = classify_response(raw)
    try:
        retain(PROVIDER, raw, url=AIRNOW_URL, outcome=outcome, detail=detail)
    except Exception as exc:
        log.error("raw retention failed for %s: %s", PROVIDER, exc, exc_info=True)

    if outcome == OUTCOME_MALFORMED:
        raise ValueError(f"unparseable AirNow response: {detail}")
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
        log.warning("AirNow returned no observations, skipping")
        return
    ts = d["ts"]
    if write_row(_db, "epa_air_quality", d, or_ignore=True):
        pm25_s = str(d["pm25_aqi"]) if d["pm25_aqi"] is not None else "n/a"
        o3_s = str(d["ozone_aqi"]) if d["ozone_aqi"] is not None else "n/a"
        log.info("epa_air_quality row written  ts=%s  PM2.5=%s  O3=%s  area=%s",
                 ts, pm25_s, o3_s, d["reporting_area"])


# ── Main loop ──────────────────────────────────────────────────────────────────
def run() -> None:
    """Collector loop.

    Behind a function so importing this module has no side effect, which is
    what makes the failure-to-outcome wiring below reachable by a test.
    """
    log.info("airnow_wx starting — Melbourne, FL reporting area")

    while not is_shutting_down():
        try:
            _write(_parse(_fetch()))
        except urllib.error.URLError as e:
            record_outcome(PROVIDER, outcome_for_exception(e), detail=str(e),
                           url=AIRNOW_URL)
            log.warning("AirNow API fetch failed: %s", e)
        except (KeyError, IndexError, ValueError) as e:
            record_outcome(PROVIDER, outcome_for_exception(e),
                           detail=f"unexpected response shape: {e}",
                           url=AIRNOW_URL)
            log.warning("Unexpected AirNow API response: %s", e)
        except sqlite3.Error as e:
            record_outcome(PROVIDER, outcome_for_exception(e), detail=repr(e))
            log.error("Derived write failed: %s", e, exc_info=True)
        except Exception as e:
            record_outcome(PROVIDER, outcome_for_exception(e), detail=repr(e),
                           url=AIRNOW_URL)
            log.error("Unexpected error: %s", e, exc_info=True)
        time.sleep(POLL_S)

    log.info("airnow_wx stopped")


if __name__ == "__main__":
    run()
