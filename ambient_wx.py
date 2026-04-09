#!/usr/bin/env python3
"""
Path:        ~/projects/enviroplus/ambient_wx.py
Description: Polls Ambient Weather API (BSWeather WS-2902) every 60 s and
             writes outdoor readings to the 'outdoor' table in enviro.db.
             Runs as a standalone service alongside enviro_dash3.py.

Changelog:
  2026-04-04 16:56:00 EDT  Initial implementation.
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

AW_API_KEY  = os.environ["AW_API_KEY"]
AW_APP_KEY  = os.environ["AW_APP_KEY"]
AW_MAC      = os.environ["AW_MAC"]
POLL_S      = 60

AW_URL = (
    f"https://api.ambientweather.net/v1/devices"
    f"?apiKey={AW_API_KEY}&applicationKey={AW_APP_KEY}"
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
    try:
        _db.execute(
            """
            INSERT OR IGNORE INTO outdoor VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ts,
                d.get("tempf"),        d.get("tempinf"),
                d.get("humidity"),     d.get("humidityin"),
                d.get("baromrelin"),   d.get("baromabsin"),
                d.get("windspeedmph"), d.get("windgustmph"),
                d.get("winddir"),
                d.get("maxdailygust"),
                d.get("solarradiation"), d.get("uv"),
                d.get("dewPoint"),     d.get("feelsLike"),
                d.get("hourlyrainin"), d.get("dailyrainin"),
                d.get("weeklyrainin"), d.get("monthlyrainin"),
                d.get("totalrainin"),
                d.get("lastRain"),
            ),
        )
        _db.commit()
        logging.info(f"outdoor row written  ts={ts}  temp={d.get('tempf')}°F  "
                     f"hum={d.get('humidity')}%  wind={d.get('windspeedmph')}mph")
    except Exception as e:
        logging.warning(f"SQLite write failed: {e}")


# ── Main loop ──────────────────────────────────────────────────────────────────
logging.info("ambient_wx starting")

while True:
    try:
        _write(_fetch())
    except urllib.error.URLError as e:
        logging.warning(f"API fetch failed: {e}")
    except (KeyError, IndexError, ValueError) as e:
        logging.warning(f"Unexpected API response: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    time.sleep(POLL_S)
