#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        nws_wx.py
PATH:        ~/projects/enviroplus/nws_wx.py
DESCRIPTION: Polls configured NWS observation stations every 10 min and writes
             observations to the 'nws_weather' table in enviro.db.
             Runs as a standalone service alongside ambient_wx.py.

CHANGELOG:
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

import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

sys.path.insert(0, "/home/pistrommy/projects")

from shared.config_service import load_env, require
from shared.db_service import connect, write_row
from shared.logging_service import setup_logger
from shared.signal_handler import install_shutdown_handler

# ── Paths / config ─────────────────────────────────────────────────────────────
_BASE       = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH   = os.path.join(_BASE, ".env")


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
    log_path: str
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
        log_path=require("LOG_PATH"),
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


def _fetch(settings: NwsSettings, station: str, now_utc: datetime) -> dict[str, Any]:
    start = (now_utc - timedelta(seconds=settings.collection_lookback_s)).isoformat()
    end = now_utc.isoformat()
    url = (
        f"{settings.api_base_url}/stations/{station}/observations"
        f"?start={start.replace('+00:00', 'Z')}&end={end.replace('+00:00', 'Z')}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": settings.user_agent})
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    observations = data["features"]
    if not observations:
        raise ValueError("NWS observations collection returned no features")
    return max(
        (feature["properties"] for feature in observations),
        key=lambda properties: _parse_observation_ts(properties["timestamp"]),
    )


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
        except (urllib.error.URLError, KeyError, IndexError, ValueError) as exc:
            failures.append(f"{station}: {exc}")
    raise NoFreshObservationError("; ".join(failures))


def _write(conn: sqlite3.Connection, logger, d: dict[str, Any]) -> bool:
    ts = d["ts"]
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
    log = setup_logger("nws_wx", settings.log_path)
    is_shutting_down = install_shutdown_handler(logger=log)
    db = connect(settings.sqlite_path)
    _ensure_schema(db)

    log.info("nws_wx starting — stations %s", ",".join(settings.stations))
    while not is_shutting_down():
        try:
            observation = _select_observation(settings, now_utc=datetime.now(UTC), logger=log)
            _write(db, log, observation)
        except NoFreshObservationError as exc:
            log.warning("No fresh NWS observation from configured stations: %s", exc)
        except Exception as exc:
            log.error("Unexpected error: %s", exc, exc_info=True)
        _sleep_until_next_poll(settings, is_shutting_down)

    log.info("nws_wx stopped")


if __name__ == "__main__":
    run()
