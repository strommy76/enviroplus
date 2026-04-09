#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        ambient_wx.py
PATH:        ~/projects/enviroplus/ambient_wx.py
DESCRIPTION: Polls Ambient Weather API (BSWeather WS-2902) every 60 s and
             writes outdoor readings to the 'outdoor' table in enviro.db.
             Runs as a standalone service alongside enviro_dash3.py.

CHANGELOG:
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
from shared.signal_handler import install_shutdown_handler

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
    req = urllib.request.urlopen(AW_URL, timeout=15)
    data = json.loads(req.read())
    return data[0]["lastData"]


def _write(d):
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
        log.warning("API fetch failed: %s", e)
    except (KeyError, IndexError, ValueError) as e:
        log.warning("Unexpected API response: %s", e)
    except Exception as e:
        log.error("Unexpected error: %s", e, exc_info=True)
    time.sleep(POLL_S)

log.info("ambient_wx stopped")
