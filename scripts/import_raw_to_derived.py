#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        import_raw_to_derived.py
PATH:        ~/projects/enviroplus/scripts/import_raw_to_derived.py
DESCRIPTION: Replays the canonical raw tier into the derived tables.

             This is the recovery property made real: the derived tables are a
             projection of raw-capture, so a hole in them is repairable from
             local disk instead of from a provider retention window nobody
             controls. It is also the piece that finally closes the gap this
             whole effort started from.

             What it can and cannot recover, measured rather than assumed:

               ambient  19 dark days at 5-minute resolution -- the history
                        endpoint's grain, 4.9x coarser than the 60s live
                        capture. Every imported day is permanently sparser
                        than a live one, which is why they are marked.
               nws      7 of 19 days. The rest aged out of a 7-day provider
                        retention window before capture, and no longer exist
                        anywhere.
               airnow   NOT imported. Its historical endpoint serves one daily
                        aggregate; writing that at a fabricated hourly
                        timestamp among hourly facts is a tier violation, and
                        the operator ruled the lane dropped. The raw is
                        retained either way.

             Every imported row carries capture_mode='backfill'. Without that
             a 5-minute row is indistinguishable from a 60-second one, and any
             consumer computing a rate over the boundary is silently wrong.

USAGE:       python3 scripts/import_raw_to_derived.py [--dry-run] [--provider ambient|nws]

CHANGELOG:
2026-08-06 17:56      Claude     [Feature] Initial implementation.
--------------------------------------------------------------------------------
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, "/home/pistrommy/projects")
sys.path.insert(0, str(_BASE))

from shared.db_service import connect, write_row  # noqa: E402

log = logging.getLogger("import_raw")

RAW_ROOT = Path(os.environ.get("ENVIRO_RAW_ROOT", _BASE / "raw-capture"))
SQLITE_PATH = os.environ.get("SQLITE_PATH", str(_BASE / "enviro.db"))
CAPTURE_MODE = "backfill"


class ImportError_(RuntimeError):
    """The import could not be performed correctly."""


# ── ambient ───────────────────────────────────────────────────────────────────

def _ambient_rows():
    """Yield outdoor rows from the retained Ambient history.

    Uses the collector's own mapping so a replayed row is built by exactly the
    code that builds a live one -- a second copy of that mapping would diverge
    silently.
    """
    import ambient_wx  # noqa: E402  (import-safe: loop is behind run())

    for path in sorted((RAW_ROOT / "ambient").glob("*.json")):
        if path.name == "MANIFEST.json":
            continue
        try:
            records = json.loads(path.read_bytes())
        except ValueError as exc:
            raise ImportError_(f"unparseable retained payload {path}: {exc}") from exc
        for rec in records:
            if "dateutc" not in rec:
                continue
            yield ambient_wx.row_from_observation(rec)


# ── nws ───────────────────────────────────────────────────────────────────────

def _nws_rows(stations: list[str]):
    """Yield nws_weather rows, one per timestamp, by station priority.

    `ts` is PRIMARY KEY, so the schema itself forbids keeping every station's
    observation. Priority order mirrors _select_observation, which returns the
    FIRST configured station that is fresh -- not the freshest across stations.
    Choosing differently would populate the gap from different physical sensors
    than the live series either side of it.
    """
    import nws_wx  # noqa: E402

    rank = {s: i for i, s in enumerate(stations)}
    best: dict[str, tuple[int, dict]] = {}

    for path in sorted((RAW_ROOT / "nws").glob("*.json")):
        if path.name == "MANIFEST.json":
            continue
        station = path.name.split("_", 1)[0]
        if station not in rank:
            log.warning("skipping %s: station not in configured priority list", path.name)
            continue
        try:
            features = json.loads(path.read_bytes()).get("features") or []
        except ValueError as exc:
            raise ImportError_(f"unparseable retained payload {path}: {exc}") from exc

        for feature in features:
            props = feature.get("properties") or {}
            if not props.get("timestamp"):
                continue
            row = nws_wx._parse(props, station)
            ts = row.get("ts")
            if ts is None:
                continue
            prior = best.get(ts)
            if prior is None or rank[station] < prior[0]:
                best[ts] = (rank[station], row)

    for _, row in best.values():
        yield row


# ── import ────────────────────────────────────────────────────────────────────

def _ensure_capture_mode(conn: sqlite3.Connection, table: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    if "capture_mode" not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN capture_mode TEXT")
        conn.execute(
            f"UPDATE {table} SET capture_mode='live' WHERE capture_mode IS NULL")
        conn.commit()


def import_table(conn, table: str, rows, *, dry_run: bool) -> Counter:
    """Insert rows, never overwriting what is already there.

    INSERT OR IGNORE on the ts PRIMARY KEY means a live row always wins over a
    replayed one. That is the correct precedence: live capture is finer-grained
    and closer to the source.
    """
    _ensure_capture_mode(conn, table)
    before = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    stats = Counter()

    for row in rows:
        stats["candidates"] += 1
        if dry_run:
            continue
        row = {**row, "capture_mode": CAPTURE_MODE}
        if write_row(conn, table, row, or_ignore=True):
            stats["inserted"] += 1
        else:
            stats["already_present"] += 1

    after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    stats["net_rows_added"] = after - before
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--provider", choices=("ambient", "nws"), action="append")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s")

    providers = args.provider or ["ambient", "nws"]
    stations = [s.strip().upper() for s in
                os.environ.get("NWS_STATIONS", "").split(",") if s.strip()]
    if "nws" in providers and not stations:
        # Fall back to the collector's own settings loader rather than guessing.
        import nws_wx
        stations = list(nws_wx.load_settings().stations)

    conn = connect(SQLITE_PATH)
    try:
        for provider in providers:
            if provider == "ambient":
                stats = import_table(conn, "outdoor", _ambient_rows(),
                                     dry_run=args.dry_run)
            else:
                stats = import_table(conn, "nws_weather", _nws_rows(stations),
                                     dry_run=args.dry_run)
            log.info("%-8s candidates=%d inserted=%d already_present=%d net=%d%s",
                     provider, stats["candidates"], stats["inserted"],
                     stats["already_present"], stats["net_rows_added"],
                     "  [dry-run]" if args.dry_run else "")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
