#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        ambient_wx.py
PATH:        ~/projects/enviroplus/ambient_wx.py
DESCRIPTION: Polls Ambient Weather API (BSWeather WS-2902) every 60 s and
             writes outdoor readings to the 'outdoor' table in enviro.db.
             Runs as a standalone service alongside enviro_dash3.py.

CHANGELOG:
2026-08-06 15:37      Claude      [Feature] Retain the provider response
                                      verbatim before parsing, and record every
                                      collection attempt. A failed pull now
                                      records an outcome instead of writing a
                                      row of nulls; an outdoor-array dropout is
                                      recorded as such while the indoor
                                      readings it still carries are kept.
2026-04-09 14:00      Claude      [Docs] Update file header to Lexx standard
                                      format
2026-04-09 00:00      Claude      [Refactor] Phase 3 refactor: use shared
                                      services library for config, logging, DB
                                      writes, and signal handling.
2026-04-04 16:56      Bryan       [Feature] Initial implementation.
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
    OUTCOME_PARTIAL,
    OUTCOME_WRITE_ERROR,
    record_outcome,
    retain,
)
from shared.signal_handler import install_shutdown_handler

PROVIDER = "ambient"

# Presence of an outdoor measurement distinguishes a full record from a
# console-only one. When the WS-2902 outdoor array drops off RF the console
# keeps reporting indoor values, and the response simply omits these keys.
_OUTDOOR_KEYS = ("tempf", "humidity", "windspeedmph", "winddir", "solarradiation")

# ── Paths / config ─────────────────────────────────────────────────────────────
_BASE       = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH   = os.path.join(_BASE, ".env")
LOG_PATH    = os.path.join(_BASE, "enviro.log")
SQLITE_PATH = os.path.join(_BASE, "enviro.db")

load_env(_ENV_PATH, expect_key="AW_API_KEY")

AW_API_KEY  = require("AW_API_KEY")
AW_APP_KEY  = require("AW_APP_KEY")
AW_MAC      = require("AW_MAC")
POLL_S      = int(require("AW_POLL_S"))

AW_URL = (
    f"https://api.ambientweather.net/v1/devices"
    f"?apiKey={AW_API_KEY}&applicationKey={AW_APP_KEY}"
)

# ── Logging ────────────────────────────────────────────────────────────────────
log = setup_logger("ambient_wx", LOG_PATH)

# ── Signal handler ─────────────────────────────────────────────────────────────
is_shutting_down = install_shutdown_handler(logger=log)

# ── SQLite ─────────────────────────────────────────────────────────────────────
_db = connect(SQLITE_PATH)
_db.execute("""
    CREATE TABLE IF NOT EXISTS outdoor (
        ts             TEXT PRIMARY KEY,
        tempf          REAL, tempinf        REAL,
        humidity       REAL, humidityin     REAL,
        baromrelin     REAL, baromabsin     REAL,
        windspeedmph   REAL, windgustmph    REAL,
        winddir        INTEGER,
        maxdailygust   REAL,
        solarradiation REAL, uv             REAL,
        dewpoint       REAL, feelslike      REAL,
        hourlyrainin   REAL, dailyrainin    REAL,
        weeklyrainin   REAL, monthlyrainin  REAL,
        totalrainin    REAL,
        lastrain       TEXT
    )
""")
_db.commit()


def _fetch():
    """Fetch, retain the bytes as received, then parse.

    Retention happens before parsing so the canonical record is what the
    provider actually sent, not what this collector understood. A retention
    failure is recorded and logged but does not suppress the derived write --
    blocking it would lose the observation in both tiers instead of one.
    """
    req = urllib.request.urlopen(AW_URL, timeout=15)
    raw = req.read()

    # Classify what arrived, then retain it once under that label. Bytes are
    # retained even when unparseable -- a malformed response is itself a fact,
    # and discarding it would lose the only evidence of what the provider sent.
    try:
        data = json.loads(raw)
        empty = not data or "lastData" not in data[0]
        outcome = OUTCOME_EMPTY if empty else OUTCOME_OK
    except ValueError as exc:
        data, empty, outcome = None, True, OUTCOME_MALFORMED
        detail = str(exc)
    else:
        detail = "response carried no lastData" if empty else None

    try:
        retain(PROVIDER, raw, url=AW_URL, outcome=outcome, detail=detail)
    except Exception as exc:
        log.error("raw retention failed for %s: %s", PROVIDER, exc, exc_info=True)

    if data is None:
        raise ValueError(f"unparseable Ambient response: {detail}")
    return None if empty else data[0]["lastData"]


def _write(d):
    if d is None:
        return

    # An outdoor-array dropout still carries valid indoor readings, so the row
    # is written with what arrived and the absence is recorded as its own fact
    # rather than left to be inferred from a column full of nulls.
    if not any(k in d for k in _OUTDOOR_KEYS):
        record_outcome(PROVIDER, OUTCOME_PARTIAL,
                       detail="outdoor array absent; console/indoor fields only")
        log.warning("outdoor array absent from response — indoor fields only")

    # dateutc is milliseconds since epoch — convert to UTC timestamp string
    ts = datetime.fromtimestamp(d["dateutc"] / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    row = {
        "ts":             ts,
        "tempf":          d.get("tempf"),
        "tempinf":        d.get("tempinf"),
        "humidity":       d.get("humidity"),
        "humidityin":     d.get("humidityin"),
        "baromrelin":     d.get("baromrelin"),
        "baromabsin":     d.get("baromabsin"),
        "windspeedmph":   d.get("windspeedmph"),
        "windgustmph":    d.get("windgustmph"),
        "winddir":        d.get("winddir"),
        "maxdailygust":   d.get("maxdailygust"),
        "solarradiation": d.get("solarradiation"),
        "uv":             d.get("uv"),
        "dewpoint":       d.get("dewPoint"),
        "feelslike":      d.get("feelsLike"),
        "hourlyrainin":   d.get("hourlyrainin"),
        "dailyrainin":    d.get("dailyrainin"),
        "weeklyrainin":   d.get("weeklyrainin"),
        "monthlyrainin":  d.get("monthlyrainin"),
        "totalrainin":    d.get("totalrainin"),
        "lastrain":       d.get("lastRain"),
    }
    if write_row(_db, "outdoor", row, or_ignore=True):
        log.info("outdoor row written  ts=%s  temp=%s°F  hum=%s%%  wind=%smph",
                 ts, d.get("tempf"), d.get("humidity"), d.get("windspeedmph"))


# ── Main loop ──────────────────────────────────────────────────────────────────
log.info("ambient_wx starting")

while not is_shutting_down():
    try:
        _write(_fetch())
    except urllib.error.URLError as e:
        record_outcome(PROVIDER, OUTCOME_FETCH_ERROR, detail=str(e), url=AW_URL)
        log.warning("API fetch failed: %s", e)
    except (KeyError, IndexError, ValueError) as e:
        record_outcome(PROVIDER, OUTCOME_FETCH_ERROR,
                       detail=f"unexpected response shape: {e}", url=AW_URL)
        log.warning("Unexpected API response: %s", e)
    except sqlite3.Error as e:
        # The payload arrived and is already retained; only the derived write
        # failed. Recording this as a fetch error would misattribute the fault.
        record_outcome(PROVIDER, OUTCOME_WRITE_ERROR, detail=repr(e))
        log.error("Derived write failed: %s", e, exc_info=True)
    except Exception as e:
        record_outcome(PROVIDER, OUTCOME_FETCH_ERROR, detail=repr(e), url=AW_URL)
        log.error("Unexpected error: %s", e, exc_info=True)
    time.sleep(POLL_S)

log.info("ambient_wx stopped")
