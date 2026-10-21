#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        local_sensors.py
PATH:        ~/projects/enviroplus/local_sensors.py
DESCRIPTION: The two tiers of the local sensor lane, and the projection from
             one to the other.

             Tier 1 (canonical): every sensor read enviro_dash3.py makes is
             retained through shared.raw_retention as provider "local_sensors",
             one record per loop, holding each driver's output exactly as
             returned. A failed read is recorded as that lane's error in the
             record, never as a value.

             Tier 2 (derived): the `readings` table. One row per publish
             interval, projected from that interval's Tier 1 records by
             derive_row() with the calibration in the dashboard config.
             Live (enviro_dash3.py) and `--replay DAY...` (here) both call it,
             so a replayed row is the row live would have written, and a
             changed calibration is applied to history by replaying.

             Rows written before Tier 1 existed (2026-10-21) have no retained
             reads. They are kept as written and never rebuilt or dropped.

CHANGELOG:
2026-10-20 22:30      Claude      [Feature] Initial: Tier 1 retention of every
                                      local sensor read, Tier 2 `readings`
                                      derived from it, --replay.
--------------------------------------------------------------------------------
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime

sys.path.insert(0, "/home/pistrommy/projects")

from shared.db_service import write_row
from shared.raw_retention import read_day

PROVIDER = "local_sensors"

# One driver reading per entry: the PMS5003 frame is retained as the bytes the
# driver checksummed, so particle counts and the atmospheric-environment
# channels survive alongside the three values readings carries.
# Standard-particle µg/m³ words, the ones pm_ug_per_m3(size) returns by default.
_PMS_STANDARD = {"pm1": 0, "pm25": 1, "pm10": 2}   # PMS5003Data.data indices

_COLUMNS = (
    ("ts", "TEXT PRIMARY KEY"),
    ("temp_f", "REAL"), ("humidity", "REAL"), ("pressure", "REAL"), ("lux", "REAL"),
    ("oxidising", "REAL"), ("reducing", "REAL"), ("ammonia", "REAL"),
    ("pm1", "REAL"), ("pm25", "REAL"), ("pm10", "REAL"),
    ("cpu_temp_c", "REAL"), ("cpu_load", "REAL"), ("mem_free_mb", "REAL"),
    ("uptime_s", "INTEGER"),
    ("co2_ppm", "REAL"), ("scd41_temp_c", "REAL"), ("scd41_rh", "REAL"),
)


def ensure_schema(db) -> None:
    """Create `readings`, or add any column an older table lacks. Additive only:
    no existing row or column changes."""
    db.execute("CREATE TABLE IF NOT EXISTS readings ("
               + ", ".join(f"{name} {typedef}" for name, typedef in _COLUMNS) + ")")
    present = {row[1] for row in db.execute("PRAGMA table_info(readings)")}
    for name, typedef in _COLUMNS:
        if name not in present:
            db.execute(f"ALTER TABLE readings ADD COLUMN {name} {typedef}")
    db.commit()


def bucket_of(read_utc: str, publish_s: int) -> int:
    """Publish interval a read belongs to: whole intervals since the epoch, UTC."""
    return int(datetime.fromisoformat(read_utc).timestamp()) // publish_s


def _r(x, n):
    """Round only real values; None (absent/failed lane) passes through as NULL."""
    return None if x is None else round(x, n)


def c2f(c):
    return c * 9 / 5 + 32


def correct_humidity(rh, raw_c, actual_c):
    """Correct BME280 RH for chip self-heating with the Magnus formula: the
    same water vapour at the room temperature instead of the warmer chip's."""
    def psat(t):
        return math.exp(17.625 * t / (243.04 + t))
    return min(rh * psat(raw_c) / psat(actual_c), 100.0)


def compensate(sample: dict, calibration: dict):
    """(room_c, chip_c) from one record's BME280 reads. Self-heating on this
    mounting is a near-constant pedestal (measured 2026-07-30), so the room
    temperature is the mean chip temperature less self_heat_offset_c."""
    chip_c = sum(b["temperature"] for b in sample["bme280"]) / len(sample["bme280"])
    return chip_c - float(calibration["self_heat_offset_c"]), chip_c


def last_with(samples: list[dict], key: str):
    """The newest sample in the interval that carries `key`, else None."""
    return next((s for s in reversed(samples) if key in s), None)


def derive_row(samples: list[dict], calibration: dict) -> dict:
    """The `readings` row for one publish interval's Tier 1 records, oldest
    first. Every lane takes its newest successful read in the interval; a lane
    with none is NULL, never a value from another interval."""
    last = samples[-1]
    room_c, chip_c = compensate(last, calibration)
    bme = last["bme280"][-1]
    gas = last["mics6814_ohms"]
    pi = last["pi"]
    row = {
        "ts": datetime.fromisoformat(last["read_utc"]).strftime("%Y-%m-%d %H:%M:%S"),
        "temp_f": _r(c2f(room_c), 1),
        "humidity": _r(correct_humidity(bme["humidity"], chip_c, room_c), 1),
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
    scd = last_with(samples, "scd41")
    row["co2_ppm"] = None if scd is None else scd["scd41"]["co2_ppm"]
    row["scd41_temp_c"] = None if scd is None else scd["scd41"]["temperature_c"]
    row["scd41_rh"] = None if scd is None else scd["scd41"]["rh"]
    return row


def _pms_words(frame_hex: str) -> tuple:
    """The frame's 14 big-endian words, the layout PMS5003Data unpacks."""
    frame = bytes.fromhex(frame_hex)
    return tuple(int.from_bytes(frame[i:i + 2], "big") for i in range(0, len(frame), 2))


def write(db, row: dict) -> None:
    """Upsert on ts: a replay under a new calibration replaces the row."""
    write_row(db, "readings", row, upsert_on="ts")


def samples_for_days(days: list[str]):
    """Yield every retained sample on the named UTC capture days, in order.
    Each record carries its own read_utc, so the store never folds one into a
    byte-identical duplicate."""
    for day in days:
        for _captured, _outcome, blob in read_day(PROVIDER, day):
            if blob is not None:
                yield json.loads(blob)


def replay(db, days: list[str], cfg: dict) -> dict:
    """Rebuild `readings` rows for the named capture days from Tier 1."""
    publish_s = cfg["intervals"]["publish_s"]
    tally = {"samples": 0, "rows": 0}
    interval, pending = None, []
    for sample in samples_for_days(days):
        tally["samples"] += 1
        b = bucket_of(sample["read_utc"], publish_s)
        if pending and b != interval:
            write(db, derive_row(pending, cfg["calibration"]))
            tally["rows"] += 1
            pending = []
        interval = b
        pending.append(sample)
    if pending:
        write(db, derive_row(pending, cfg["calibration"]))
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
    from shared.raw_retention import configure as configure_retention

    parser = argparse.ArgumentParser(description="Local sensor lane: Tier 2 replay.")
    parser.add_argument("--replay", nargs="+", metavar="DAY", type=_utc_day, required=True,
                        help="rebuild `readings` rows from reads retained on these UTC days, "
                             "with the calibration in the CONFIG_PATH document, and exit")
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
