#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        local_sensors.py
PATH:        ~/projects/enviroplus/local_sensors.py
DESCRIPTION: The two tiers of the local sensor lane, and the projection from
             one to the other.

             Tier 1 (canonical): every sensor read enviro_dash3.py makes is
             retained through raw_retention as provider "local_sensors",
             one record per loop, holding each driver's output exactly as
             returned. A failed read is recorded as that lane's error in the
             record, never as a value.

             Tier 2 (derived): the `readings` table. One row per publish
             interval, projected from that interval's Tier 1 records by
             derive_row() under the current sensor roles.
             Live (enviro_dash3.py) and `--replay DAY...` (here) both call it,
             and a row is keyed by its interval's start, so replaying a day
             rewrites that day's rows using current roles/publish_s. Records
             without TMP119 have NULL room temperature; history is never inferred. Where live and replay differ, a
             process restart is the cause: live never writes the interval open
             at shutdown, and writes the interval open at restart from its
             post-restart reads only; replay writes both from all their reads.

             Rows from before the first local_sensors record have no retained
             reads. They are kept as written and never rebuilt or dropped.

CHANGELOG:
2026-10-20 22:30      Claude      [Feature] Initial: Tier 1 retention of every
                                      local sensor read, Tier 2 `readings`
                                      derived from it, --replay.
--------------------------------------------------------------------------------
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, "/home/pistrommy/projects")

from shared.db_service import write_row

from raw_retention import days as retained_days
from raw_retention import read_day

PROVIDER = "local_sensors"

# One driver reading per entry: the PMS5003 frame body is retained as
# PMS5003Data.raw_data, the 28 bytes (14 big-endian words, checksum last) after
# the 0x42 0x4D start bytes and length word, which pms5003 1.0.1 reads and
# checksums separately. So particle counts and the atmospheric-environment
# channels survive alongside the three values readings carries.
# Standard-particle µg/m³ words, the ones pm_ug_per_m3(size) returns by default.
_PMS_STANDARD = {"pm1": 0, "pm25": 1, "pm10": 2}  # PMS5003Data.data indices

_COLUMNS = (
    ("ts", "TEXT PRIMARY KEY"),
    ("temp_f", "REAL"),
    ("humidity", "REAL"),
    ("pressure", "REAL"),
    ("lux", "REAL"),
    ("oxidising", "REAL"),
    ("reducing", "REAL"),
    ("ammonia", "REAL"),
    ("pm1", "REAL"),
    ("pm25", "REAL"),
    ("pm10", "REAL"),
    ("cpu_temp_c", "REAL"),
    ("cpu_load", "REAL"),
    ("mem_free_mb", "REAL"),
    ("uptime_s", "INTEGER"),
    ("co2_ppm", "REAL"),
    ("scd41_temp_c", "REAL"),
    ("scd41_rh", "REAL"),
)


def ensure_schema(db) -> None:
    """Create `readings`, or add any column an older table lacks. Additive only:
    no existing row or column changes."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS readings ("
        + ", ".join(f"{name} {typedef}" for name, typedef in _COLUMNS)
        + ")"
    )
    present = {row[1] for row in db.execute("PRAGMA table_info(readings)")}
    for name, typedef in _COLUMNS:
        if name not in present:
            db.execute(f"ALTER TABLE readings ADD COLUMN {name} {typedef}")
    db.commit()


def bucket_of(read_utc: str, publish_s: int) -> int:
    """Publish interval a read belongs to: whole intervals since the epoch, UTC."""
    return int(datetime.fromisoformat(read_utc).timestamp()) // publish_s


def interval_start(bucket: int, publish_s: int) -> datetime:
    return datetime.fromtimestamp(bucket * publish_s, timezone.utc)


def _r(x, n):
    """Round only real values; None (absent/failed lane) passes through as NULL."""
    return None if x is None else round(x, n)


def c2f(c):
    return c * 9 / 5 + 32


def last_with(samples: list[dict], key: str):
    """The newest sample in the interval that carries `key`, else None."""
    return next((s for s in reversed(samples) if key in s), None)


def derive_row(samples: list[dict], publish_s: int) -> dict:
    """The `readings` row for one publish interval's Tier 1 records, oldest
    first, keyed by the interval's start (UTC) on the publish_s grid that
    grouped them. Every lane takes its newest successful read in the interval;
    a lane with none is NULL, never a value from another interval."""
    last = samples[-1]
    start = interval_start(bucket_of(last["read_utc"], publish_s), publish_s)
    tmp = last_with(samples, "tmp119")
    scd = last_with(samples, "scd41")
    bme = last["bme280"][-1]
    gas = last["mics6814_ohms"]
    pi = last["pi"]
    row = {
        "ts": _ts(start),
        "temp_f": None if tmp is None else c2f(tmp["tmp119"]["temperature_c"]),
        "humidity": None if scd is None else scd["scd41"]["rh"],
        "pressure": _r(bme["pressure"], 2),
        "lux": _r(last["ltr559_lux"], 1),
        "oxidising": _r(gas["oxidising"] / 1000, 1),
        "reducing": _r(gas["reducing"] / 1000, 1),
        "ammonia": _r(gas["nh3"] / 1000, 1),
        "cpu_temp_c": _r(last["cpu_temp_milli_c"] / 1000, 1),
        "cpu_load": _r(pi["loadavg_1m"], 2),
        "mem_free_mb": _r(pi["mem_available_kb"] / 1024, 1),
        "uptime_s": int(pi["uptime_s"]),
    }
    pms = last_with(samples, "pms5003_frame_hex")
    words = None if pms is None else _pms_words(pms["pms5003_frame_hex"])
    for column, index in _PMS_STANDARD.items():
        row[column] = None if words is None else float(words[index])
    row["co2_ppm"] = None if scd is None else scd["scd41"]["co2_ppm"]
    row["scd41_temp_c"] = None if scd is None else scd["scd41"]["temperature_c"]
    row["scd41_rh"] = None if scd is None else scd["scd41"]["rh"]
    return row


def _pms_words(frame_hex: str) -> tuple:
    """The frame's 14 big-endian words, the layout PMS5003Data unpacks."""
    frame = bytes.fromhex(frame_hex)
    return tuple(int.from_bytes(frame[i : i + 2], "big") for i in range(0, len(frame), 2))


def write(db, row: dict) -> None:
    """Insert; an existing row at the same ts is never overwritten. Replay
    clears its span first, so it rewrites; live writes each interval once, and
    a row from before Tier 1 that happens to share a key is kept."""
    write_row(db, "readings", row, or_ignore=True)


def _day_samples(day: str):
    """Every sample read on UTC `day`, in retention order. A record is filed
    under the day it was retained, so a read just before midnight can be in
    the next day's file; that file is read only until its reads pass `day`.
    Each record carries its own read_utc, so none is ever folded into a
    byte-identical duplicate."""
    following = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    for file_day in (day, following):
        for _captured, _outcome, blob in read_day(PROVIDER, file_day):
            if blob is None:
                continue
            sample = json.loads(blob)
            read_day_ = sample["read_utc"][:10]
            if read_day_ == day:
                yield sample
            elif file_day == following and read_day_ > day:
                break


def _first_retained_read() -> str | None:
    """`ts`-form time of the first read Tier 1 holds: rows before it predate
    Tier 1 and have nothing to be rebuilt from."""
    for day in retained_days(PROVIDER):
        for sample in _day_samples(day):
            return _ts(datetime.fromisoformat(sample["read_utc"]))
    return None


def _ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def replay(db, days: list[str], cfg: dict) -> dict:
    """Rebuild `readings` for the named UTC days from Tier 1, with the current
    sensor roles and publish_s grid. Missing TMP119 history yields NULL temperature.

    Each day is read through once first, so a corrupt or unverifiable record
    fails the replay before any row is touched. Then the day's rows are
    deleted and rewritten, streaming one interval at a time: rows on a
    since-changed grid go too. A derive_row error partway through leaves the
    rest of that day deleted until it is fixed and replayed; live runs the
    same derive_row on the same records, so such a record would already have
    stopped live.
    Rows from before the first read Tier 1 holds are never deleted, so the
    interval that read falls in keeps the row live wrote for it.
    Assumes publish_s divides a day (it is 60): an interval spanning UTC
    midnight would be derived without its post-midnight reads."""
    publish_s = cfg["intervals"]["publish_s"]
    cutover = _first_retained_read()
    tally = {"samples": 0, "rows": 0}
    for day in days:
        first = None
        for sample in _day_samples(day):  # validation pass
            first = first or sample["read_utc"]
        if first is None:
            continue
        following = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        # From the day's start: under Tier 1 nothing but a row on a since-changed
        # grid can sit before the day's first read.
        lower = max(f"{day} 00:00:00", cutover)
        db.execute("DELETE FROM readings WHERE ts >= ? AND ts < ?", (lower, following))
        interval, pending = None, []
        for sample in _day_samples(day):
            b = bucket_of(sample["read_utc"], publish_s)
            if pending and b != interval:
                write(db, derive_row(pending, publish_s))
                tally["rows"] += 1
                pending = []
            interval = b
            pending.append(sample)
            tally["samples"] += 1
        if pending:
            write(db, derive_row(pending, publish_s))
            tally["rows"] += 1
    return tally


def _utc_day(text: str) -> str:
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a UTC day in YYYY-MM-DD form") from None


def main(argv: list[str] | None = None) -> None:
    from shared.config_service import load_env, require
    from shared.db_service import connect

    from raw_retention import configure as configure_retention

    parser = argparse.ArgumentParser(description="Local sensor lane: Tier 2 replay.")
    parser.add_argument(
        "--replay",
        nargs="+",
        metavar="DAY",
        type=_utc_day,
        required=True,
        help="rebuild derived readings on these UTC days using current sensor roles "
        "and CONFIG_PATH publish_s. Records without TMP119 yield NULL temperature; "
        "only-copy pre-retention rows are preserved.",
    )
    args = parser.parse_args(argv)
    base = os.path.dirname(os.path.abspath(__file__))
    load_env(os.path.join(base, ".env"), expect_key="SQLITE_PATH")
    configure_retention(os.environ.get("ENVIRO_RAW_ROOT", os.path.join(base, "raw-capture")))
    with open(require("CONFIG_PATH")) as f:
        cfg = json.load(f)
    db = connect(require("SQLITE_PATH"))
    ensure_schema(db)
    print(json.dumps(replay(db, args.replay, cfg)))


if __name__ == "__main__":
    main()
