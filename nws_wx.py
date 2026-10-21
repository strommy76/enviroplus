#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        nws_wx.py
PATH:        ~/projects/enviroplus/nws_wx.py
DESCRIPTION: Polls configured NWS observation stations and writes the newest
             fresh observation to the 'nws_weather' table. Every response body
             received is retained verbatim first (an HTTP error raised
             before a body is read is recorded as fetch_error). `--replay DAY...` rebuilds rows from
             retained responses through the same parse and write.

CHANGELOG:
2026-10-11 15:50      Claude      [Fix] Classify the response before retaining
                                      it and never raise doing so, so a non-JSON
                                      or wrongly shaped body is retained as
                                      malformed instead of recorded as "never
                                      arrived"; own log file; add --replay so
                                      'nws_weather' is rebuildable from
                                      retention.
2026-05-22 03:30      Codex      [Fix] Add configured multi-station freshness
                                      selection, station provenance, import-safe
                                      service entrypoint, and duplicate-aware
                                      logging for stale NWS latest observations.
2026-05-22 03:30      Codex      [Fix] Add configured shutdown check cadence so
                                      systemd stops do not wait for the full NWS
                                      poll interval.
2026-05-22 03:30      Codex      [Fix] Poll the bounded NWS observations
                                      collection and select the newest record
                                      instead of trusting the lagging /latest
                                      shortcut.
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

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

sys.path.insert(0, "/home/pistrommy/projects")

from shared.config_service import load_env, require
from shared.db_service import connect, write_row
from shared.logging_service import setup_logger
from raw_retention import (
    OutcomeAlreadyRecorded,
    RetentionWriteError,
    configure as configure_retention,
    OUTCOME_EMPTY,
    OUTCOME_FETCH_ERROR,
    OUTCOME_MALFORMED,
    OUTCOME_OK,
    OUTCOME_WRITE_ERROR,
    read_day,
    record_outcome,
    retain,
)
from shared.signal_handler import install_shutdown_handler

PROVIDER = "nws"

# run() attaches handlers to this same named logger via setup_logger; module
# level functions resolve to the identical object once the service is running.
log = logging.getLogger("nws_wx")


def outcome_for_exception(exc: BaseException) -> str:
    """Map a raised failure to the cause it actually represents.

    Outcomes are causes, not severities: a failed derived write is not a failed
    fetch, and recording it as one would make the canonical store show a
    provider outage that never happened.
    """
    if isinstance(exc, sqlite3.Error):
        return OUTCOME_WRITE_ERROR
    return OUTCOME_FETCH_ERROR

# ── Paths / config ─────────────────────────────────────────────────────────────
_BASE       = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH   = os.path.join(_BASE, ".env")
LOG_PATH    = os.path.join(_BASE, "nws_wx.log")
# PROVISIONAL: request timeout. Settle from observed NWS response latency
# (p99 of urlopen duration) once logged.
REQUEST_TIMEOUT_S = 15


@dataclass(frozen=True)
class NwsSettings:
    """Runtime configuration loaded from the enviroplus .env SSOT."""

    api_base_url: str
    stations: tuple[str, ...]
    user_agent: str
    poll_s: int
    shutdown_check_s: int
    max_observation_age_s: int
    collection_lookback_s: int
    sqlite_path: str


class NoFreshObservationError(RuntimeError):
    """Raised when configured NWS stations do not provide a fresh observation."""


def _parse_positive_int(raw: str, key: str) -> int:
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _parse_stations(raw: str) -> tuple[str, ...]:
    stations = tuple(station.strip().upper() for station in raw.split(",") if station.strip())
    if not stations:
        raise ValueError("NWS_STATIONS must contain at least one station identifier")
    return stations


def load_settings(env_path: str = _ENV_PATH) -> NwsSettings:
    """Load NWS runtime settings from .env with no ambient defaults."""
    load_env(env_path, expect_key="NWS_STATIONS")
    max_observation_age_s = _parse_positive_int(
        require("NWS_MAX_OBSERVATION_AGE_S"),
        "NWS_MAX_OBSERVATION_AGE_S",
    )
    collection_lookback_s = _parse_positive_int(
        require("NWS_COLLECTION_LOOKBACK_S"),
        "NWS_COLLECTION_LOOKBACK_S",
    )
    if collection_lookback_s < max_observation_age_s:
        raise ValueError("NWS_COLLECTION_LOOKBACK_S must cover NWS_MAX_OBSERVATION_AGE_S")

    return NwsSettings(
        api_base_url=require("NWS_API_BASE_URL").rstrip("/"),
        stations=_parse_stations(require("NWS_STATIONS")),
        user_agent=require("NWS_USER_AGENT"),
        poll_s=_parse_positive_int(require("NWS_POLL_S"), "NWS_POLL_S"),
        shutdown_check_s=_parse_positive_int(
            require("NWS_SHUTDOWN_CHECK_S"),
            "NWS_SHUTDOWN_CHECK_S",
        ),
        max_observation_age_s=max_observation_age_s,
        collection_lookback_s=collection_lookback_s,
        sqlite_path=require("SQLITE_PATH"),
    )


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nws_weather (
            ts              TEXT PRIMARY KEY,
            station_id      TEXT,
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
    columns = {row[1] for row in conn.execute("PRAGMA table_info(nws_weather)").fetchall()}
    if "station_id" not in columns:
        conn.execute("ALTER TABLE nws_weather ADD COLUMN station_id TEXT")
    if "capture_mode" not in columns:
        # NULL states unknown provenance; no backfill may claim otherwise.
        conn.execute("ALTER TABLE nws_weather ADD COLUMN capture_mode TEXT")
    conn.commit()


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


def classify_response(raw: bytes):
    """Decide what arrived. Never raises: the response is retained with the
    outcome this returns, so nothing about its shape may stop retention.

    Returns (newest_observation_properties_or_None, outcome, detail).
    """
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return None, OUTCOME_MALFORMED, str(exc)
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        return None, OUTCOME_MALFORMED, "response carried no features list"
    if not features:
        return None, OUTCOME_EMPTY, "observations collection returned no features"
    try:
        newest = max((f["properties"] for f in features),
                     key=lambda p: _parse_observation_ts(p["timestamp"]))
    except (KeyError, TypeError, ValueError) as exc:
        return None, OUTCOME_MALFORMED, f"feature without a usable timestamp: {exc!r}"
    return newest, OUTCOME_OK, None


def _fetch(settings: NwsSettings, station: str, now_utc: datetime) -> dict[str, Any]:
    start = (now_utc - timedelta(seconds=settings.collection_lookback_s)).isoformat()
    end = now_utc.isoformat()
    url = (
        f"{settings.api_base_url}/stations/{station}/observations"
        f"?start={start.replace('+00:00', 'Z')}&end={end.replace('+00:00', 'Z')}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": settings.user_agent})
    raw = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S).read()
    # Retain before using: the canonical record is the provider's response,
    # not the single observation this collector selects from it. The station is
    # part of the provider key so per-station history stays separable.
    newest, outcome, detail = classify_response(raw)
    # A response the canonical tier could not store raises RetentionWriteError
    # here, before any derived row is written from it.
    retain(f"{PROVIDER}/{station}", raw, url=url, outcome=outcome, detail=detail)
    if newest is None:
        # Already recorded with its outcome; no second record for this attempt.
        raise OutcomeAlreadyRecorded(f"{station}: {detail}")
    return newest


def _parse(p: dict[str, Any], station: str) -> dict[str, Any]:
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
        "station_id":       station,
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


def _parse_observation_ts(ts: str) -> datetime:
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("NWS observation timestamp must include timezone")
    return parsed.astimezone(UTC)


def _observation_age_s(ts: str, now_utc: datetime) -> float:
    return (now_utc - _parse_observation_ts(ts)).total_seconds()


def _select_observation(
    settings: NwsSettings,
    *,
    now_utc: datetime,
    logger,
    fetcher: Callable[[NwsSettings, str, datetime], dict[str, Any]] = _fetch,
) -> dict[str, Any]:
    failures: list[str] = []
    for station in settings.stations:
        try:
            observation = _parse(fetcher(settings, station, now_utc), station)
            ts = observation["ts"]
            if ts is None:
                failures.append(f"{station}: missing timestamp")
                continue
            age_s = _observation_age_s(ts, now_utc)
            if age_s < 0:
                failures.append(f"{station}: future timestamp {ts}")
                continue
            if age_s > settings.max_observation_age_s:
                failures.append(f"{station}: stale timestamp {ts} age_s={age_s:.0f}")
                continue
            if failures:
                logger.warning(
                    "NWS using station %s after earlier station failures: %s",
                    station,
                    "; ".join(failures),
                )
            return observation
        except OutcomeAlreadyRecorded as exc:
            failures.append(str(exc))
        except (urllib.error.URLError, KeyError, IndexError, ValueError) as exc:
            # The attempt is a fact even when nothing came back. A network
            # failure raises before retain() is reached, so without this the
            # store holds no evidence the poll occurred.
            record_outcome(f"{PROVIDER}/{station}", OUTCOME_FETCH_ERROR,
                           detail=str(exc))
            failures.append(f"{station}: {exc}")
    raise NoFreshObservationError("; ".join(failures))


def _write(conn: sqlite3.Connection, logger, d: dict[str, Any],
           capture_mode: str = "live") -> bool:
    ts = d["ts"]
    d = {**d, "capture_mode": capture_mode}
    if ts is None:
        logger.warning("NWS observation has no timestamp, skipping")
        return False
    if write_row(conn, "nws_weather", d, or_ignore=True):
        temp_s = f"{d['temp_f']:.1f}°F" if d["temp_f"] is not None else "n/a"
        wind_s = f"{d['wind_speed_mph']:.1f}mph" if d["wind_speed_mph"] is not None else "calm"
        logger.info(
            "nws_weather row written  station=%s  ts=%s  temp=%s  wind=%s  cond=%s",
            d["station_id"],
            ts,
            temp_s,
            wind_s,
            d["conditions"],
        )
        return True
    logger.debug("nws_weather row already present  station=%s  ts=%s", d["station_id"], ts)
    return False


def _sleep_until_next_poll(settings: NwsSettings, is_shutting_down: Callable[[], bool]) -> None:
    remaining_s = settings.poll_s
    while remaining_s > 0 and not is_shutting_down():
        sleep_s = min(settings.shutdown_check_s, remaining_s)
        time.sleep(sleep_s)
        remaining_s -= sleep_s


# ── Main loop ──────────────────────────────────────────────────────────────────
def run() -> None:
    settings = load_settings()
    # Retention is configured at service start, not during config loading.
    # Loading config is something non-runtime callers legitimately do, and
    # pointing the canonical root at production from there gives any of them
    # write access to the live tier.
    configure_retention(os.environ.get(
        "ENVIRO_RAW_ROOT", os.path.join(_BASE, "raw-capture")))
    log = setup_logger("nws_wx", LOG_PATH)
    is_shutting_down = install_shutdown_handler(logger=log)
    db = connect(settings.sqlite_path)
    _ensure_schema(db)

    log.info("nws_wx starting — stations %s", ",".join(settings.stations))
    while not is_shutting_down():
        try:
            observation = _select_observation(settings, now_utc=datetime.now(UTC), logger=log)
            _write(db, log, observation)
        except RetentionWriteError:
            # The canonical tier is not storing: no row may be derived, and
            # the outcome cannot be recorded. End the process so the unit's
            # restart and OnFailure policy surface it.
            raise
        except NoFreshObservationError as exc:
            # Every configured station failed or went stale. Per-station causes
            # are already recorded; this records the cycle-level outcome, so a
            # whole-lane outage is visible as its own fact rather than only as
            # an absence of rows.
            record_outcome(PROVIDER, OUTCOME_FETCH_ERROR,
                           detail=f"no fresh observation from any station: {exc}")
            log.warning("No fresh NWS observation from configured stations: %s", exc)
        except Exception as exc:
            record_outcome(PROVIDER, outcome_for_exception(exc), detail=repr(exc))
            log.error("Unexpected error: %s", exc, exc_info=True)
        _sleep_until_next_poll(settings, is_shutting_down)

    log.info("nws_wx stopped")


def replay(settings: NwsSettings, conn: sqlite3.Connection, days: list[str]) -> dict:
    """Rebuild 'nws_weather' rows from responses retained on the named UTC
    capture days. Responses from every configured station are taken in capture
    order, as live received them; each yields its newest observation when it
    was fresh at capture time, judged exactly as live judges it, and the first
    row written for a timestamp stands, as it does live. Live fetches a
    fallback station only when the stations before it failed, so this
    reproduces live's station choice. Rows already present are kept."""
    tally = Counter()
    received = []
    for station in settings.stations:
        for day in days:
            for captured, _recorded, blob in read_day(f"{PROVIDER}/{station}", day):
                received.append((datetime.fromisoformat(captured), station, blob))
    received.sort(key=lambda r: r[0])
    for captured, station, blob in received:
        tally["records"] += 1
        if blob is None:
            tally["without_payload"] += 1
            continue
        newest, outcome, _detail = classify_response(blob)
        tally[outcome] += 1
        if newest is None:
            continue
        observation = _parse(newest, station)
        if not 0 <= _observation_age_s(observation["ts"], captured) <= settings.max_observation_age_s:
            tally["not_fresh_at_capture"] += 1
            continue
        if _write(conn, log, observation, capture_mode="replay"):
            tally["written"] += 1
    return dict(tally)


def _utc_day(text: str) -> str:
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a UTC day in YYYY-MM-DD form") from None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="NWS observation collector.")
    parser.add_argument("--replay", nargs="+", metavar="DAY", type=_utc_day,
                        help="rebuild 'nws_weather' rows from responses retained on these UTC "
                             "capture days and exit; writes to the database named by SQLITE_PATH; "
                             "include the following day to cover observations captured after "
                             "midnight UTC")
    args = parser.parse_args(argv)
    if not args.replay:
        run()
        return
    settings = load_settings()
    configure_retention(os.environ.get("ENVIRO_RAW_ROOT", os.path.join(_BASE, "raw-capture")))
    conn = connect(settings.sqlite_path)
    _ensure_schema(conn)
    print(json.dumps(replay(settings, conn, args.replay)))


if __name__ == "__main__":
    main()
