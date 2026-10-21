#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        ambient_wx.py
PATH:        ~/projects/enviroplus/ambient_wx.py
DESCRIPTION: Polls the Ambient Weather API for the configured station
             (AW_MAC), retains every response body received verbatim (an
             HTTP error raised before a body is read is recorded as
             fetch_error), and writes the
             observation to the 'outdoor' table. `--replay DAY...` rebuilds
             rows from retained responses through the same mapping and write.

CHANGELOG:
2026-10-11 15:40      Claude      [Fix] Classification never raises, so every
                                      response is retained before anything can
                                      fail; select the device by AW_MAC instead
                                      of the first on the account; a partial
                                      response is one record, not ok + partial;
                                      .env loads before any path is read and
                                      import has no side effect; own log file;
                                      add --replay so 'outdoor' is rebuildable.
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

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, "/home/pistrommy/projects")

from shared.config_service import load_env, require
from shared.db_service import connect, write_row
from shared.logging_service import setup_logger
from shared.signal_handler import install_shutdown_handler

from raw_retention import (
    OUTCOME_EMPTY,
    OUTCOME_FETCH_ERROR,
    OUTCOME_MALFORMED,
    OUTCOME_OK,
    OUTCOME_PARTIAL,
    OUTCOME_WRITE_ERROR,
    OutcomeAlreadyRecorded,
    RetentionWriteError,
    read_day,
    record_outcome,
    retain,
)
from raw_retention import (
    configure as configure_retention,
)

PROVIDER = "ambient"
_BASE = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_BASE, ".env")
LOG_PATH = os.path.join(_BASE, "ambient_wx.log")
# PROVISIONAL: request timeout. Settle from observed Ambient response latency
# (p99 of urlopen duration) once logged.
REQUEST_TIMEOUT_S = 15

# Presence of an outdoor measurement distinguishes a full record from a
# console-only one. When the WS-2902 outdoor array drops off RF the console
# keeps reporting indoor values, and the response simply omits these keys.
_OUTDOOR_KEYS = ("tempf", "humidity", "windspeedmph", "winddir", "solarradiation")


def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute("""
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
            lastrain       TEXT,
            capture_mode   TEXT
        )
    """)
    db.commit()


def classify_response(raw: bytes, mac: str):
    """Decide what arrived. Never raises: every response is retained with the
    outcome this returns, so nothing about its shape may stop retention.

    Returns (observation_or_None, outcome, detail).
    """
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return None, OUTCOME_MALFORMED, str(exc)
    if not isinstance(data, list) or not all(isinstance(d, dict) for d in data):
        return None, OUTCOME_MALFORMED, f"expected a device list, got {type(data).__name__}"
    device = next((d for d in data if str(d.get("macAddress", "")).lower() == mac.lower()), None)
    if device is None:
        return None, OUTCOME_EMPTY, "configured station (AW_MAC) not in the device list"
    observation = device.get("lastData")
    if not isinstance(observation, dict) or "dateutc" not in observation:
        return None, OUTCOME_EMPTY, "configured station carried no lastData"
    if not has_outdoor_reading(observation):
        # The indoor readings are still valid; the row is written and the
        # absence is the recorded outcome of this one attempt.
        return observation, OUTCOME_PARTIAL, "outdoor array absent; console/indoor fields only"
    return observation, OUTCOME_OK, None


def outcome_for_exception(exc: BaseException) -> str:
    """Map a raised failure to the cause it actually represents.

    Outcomes are causes, not severities: a failed derived write is not a failed
    fetch, and recording it as one would make the canonical store lie about
    which subsystem broke.
    """
    if isinstance(exc, sqlite3.Error):
        return OUTCOME_WRITE_ERROR
    return OUTCOME_FETCH_ERROR


def has_outdoor_reading(d: dict) -> bool:
    """Whether the outdoor sensor array reported at all."""
    return any(k in d for k in _OUTDOOR_KEYS)


def row_from_observation(d: dict) -> dict:
    """Map a provider observation to an `outdoor` row. Live and replay both
    call this, so a replayed row is the row live would have written."""
    # dateutc is milliseconds since epoch
    ts = datetime.fromtimestamp(d["dateutc"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "ts": ts,
        "tempf": d.get("tempf"),
        "tempinf": d.get("tempinf"),
        "humidity": d.get("humidity"),
        "humidityin": d.get("humidityin"),
        "baromrelin": d.get("baromrelin"),
        "baromabsin": d.get("baromabsin"),
        "windspeedmph": d.get("windspeedmph"),
        "windgustmph": d.get("windgustmph"),
        "winddir": d.get("winddir"),
        "maxdailygust": d.get("maxdailygust"),
        "solarradiation": d.get("solarradiation"),
        "uv": d.get("uv"),
        "dewpoint": d.get("dewPoint"),
        "feelslike": d.get("feelsLike"),
        "hourlyrainin": d.get("hourlyrainin"),
        "dailyrainin": d.get("dailyrainin"),
        "weeklyrainin": d.get("weeklyrainin"),
        "monthlyrainin": d.get("monthlyrainin"),
        "totalrainin": d.get("totalrainin"),
        "lastrain": d.get("lastRain"),
    }


def write(db, observation: dict, capture_mode: str) -> bool:
    row = {**row_from_observation(observation), "capture_mode": capture_mode}
    return write_row(db, "outdoor", row, or_ignore=True)


def replay(db, days: list[str]) -> dict:
    """Rebuild 'outdoor' rows from the responses retained on the named capture
    days (UTC). Rows already present are left as they are (same key, same
    mapping); missing rows are written with capture_mode 'replay'."""
    mac = require("AW_MAC")
    tally = Counter()
    for day in days:
        for _captured, _recorded, blob in read_day(PROVIDER, day):
            tally["records"] += 1
            if blob is None:
                tally["without_payload"] += 1
                continue
            observation, outcome, _detail = classify_response(blob, mac)
            tally[outcome] += 1
            if observation is not None and write(db, observation, "replay"):
                tally["written"] += 1
    return dict(tally)


def _fetch(url: str, mac: str, log):
    """Fetch, retain the bytes as received with their outcome, then return the
    observation (None when the response carried none)."""
    raw = urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_S).read()
    observation, outcome, detail = classify_response(raw, mac)
    # A response the canonical tier could not store raises RetentionWriteError
    # here, before any derived row is written from it.
    retain(PROVIDER, raw, url=url, outcome=outcome, detail=detail)
    if outcome == OUTCOME_MALFORMED:
        # Recorded above; the loop must not record a second outcome for it.
        raise OutcomeAlreadyRecorded(f"unparseable Ambient response: {detail}")
    if outcome != OUTCOME_OK and detail:
        log.warning("%s", detail)
    return observation


def run() -> None:
    log = setup_logger("ambient_wx", LOG_PATH)
    load_env(_ENV_PATH, expect_key="AW_API_KEY")
    configure_retention(os.environ.get("ENVIRO_RAW_ROOT", os.path.join(_BASE, "raw-capture")))
    mac = require("AW_MAC")
    poll_s = int(require("AW_POLL_S"))
    url = (
        "https://api.ambientweather.net/v1/devices"
        f"?apiKey={require('AW_API_KEY')}&applicationKey={require('AW_APP_KEY')}"
    )
    db = connect(require("SQLITE_PATH"))
    ensure_schema(db)
    is_shutting_down = install_shutdown_handler(logger=log)
    log.info("ambient_wx starting")

    while not is_shutting_down():
        try:
            observation = _fetch(url, mac, log)
            if observation is not None and write(db, observation, "live"):
                log.info(
                    "outdoor row written  ts=%s  temp=%s°F  hum=%s%%  wind=%smph",
                    row_from_observation(observation)["ts"],
                    observation.get("tempf"),
                    observation.get("humidity"),
                    observation.get("windspeedmph"),
                )
        except RetentionWriteError:
            # The canonical tier is not storing: no row may be derived, and
            # the outcome cannot be recorded. End the process so the unit's
            # restart and OnFailure policy surface it.
            raise
        except OutcomeAlreadyRecorded as e:
            log.warning("%s", e)
        except urllib.error.URLError as e:
            record_outcome(PROVIDER, outcome_for_exception(e), detail=str(e), url=url)
            log.warning("API fetch failed: %s", e)
        except sqlite3.Error as e:
            # The payload arrived and is already retained; only the derived
            # write failed.
            record_outcome(PROVIDER, outcome_for_exception(e), detail=repr(e))
            log.error("Derived write failed: %s", e, exc_info=True)
        except Exception as e:
            record_outcome(PROVIDER, outcome_for_exception(e), detail=repr(e), url=url)
            log.error("Unexpected error: %s", e, exc_info=True)
        time.sleep(poll_s)

    log.info("ambient_wx stopped")


def _utc_day(text: str) -> str:
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a UTC day in YYYY-MM-DD form") from None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ambient Weather collector.")
    parser.add_argument(
        "--replay",
        nargs="+",
        metavar="DAY",
        type=_utc_day,
        help="rebuild 'outdoor' rows from responses retained on these UTC capture "
        "days and exit; writes to the database named by SQLITE_PATH; "
        "include the following day to cover observations captured after "
        "midnight UTC",
    )
    args = parser.parse_args(argv)
    if not args.replay:
        run()
        return
    load_env(_ENV_PATH, expect_key="AW_API_KEY")
    configure_retention(os.environ.get("ENVIRO_RAW_ROOT", os.path.join(_BASE, "raw-capture")))
    db = connect(require("SQLITE_PATH"))
    ensure_schema(db)
    print(json.dumps(replay(db, args.replay)))


if __name__ == "__main__":
    main()
