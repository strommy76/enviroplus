"""
--------------------------------------------------------------------------------
FILE:        test_dash_loop.py
PATH:        ~/projects/enviroplus/tests/test_dash_loop.py
DESCRIPTION: Runs the real enviro_dash3.py loop against a temporary database
             and retention root, with the hardware drivers replaced by
             stand-ins that return what the real drivers return (or raise what
             they raise), and checks what reaches Tier 1 (raw retention) and
             Tier 2 (the readings table).

CHANGELOG:
2026-10-20 22:30      Claude      [Feature] Tier 1 records every read as its
                                      driver returned it; readings is derived
                                      from it and replay reproduces it. SCD41
                                      samples stored once, gaps NULL, I2C
                                      errors recorded without ending the loop.
2026-10-11 15:20      Claude      [Feature] Failed PM read stored as NULL;
                                      loop errors end the process.
--------------------------------------------------------------------------------
"""

import itertools
import json
import os
import runpy
import shutil
import sqlite3
import struct
import sys
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

READINGS = (
    "ts, temp_f, humidity, pressure, lux, oxidising, reducing, ammonia, pm1, pm25, pm10,"
    " cpu_temp_c, cpu_load, mem_free_mb, uptime_s, co2_ppm, scd41_temp_c, scd41_rh"
)


class _Stop(BaseException):
    """Ends the loop from the sleep stand-in without looking like an error."""


class ReadTimeoutError(Exception):
    pass


class I2cError(IOError):
    """sensirion_i2c_driver.errors.I2cError subclasses IOError."""


def frame(pm1, pm25, pm10):
    """A PMS5003 data frame: 14 big-endian words, standard-particle µg/m³ first,
    then the atmospheric-environment ones (distinct here, so a mix-up shows)."""
    return struct.pack(
        ">14H", pm1, pm25, pm10, pm1 + 10, pm25 + 10, pm10 + 10, 300, 90, 20, 4, 1, 0, 0, 0
    )


class Signal:
    """What the Sensirion driver's read_measurement returns: objects whose
    .value is the converted reading."""

    def __init__(self, value):
        self.value = value


def _install_drivers(
    monkeypatch,
    pms_reads,
    gas_reads,
    scd41_reads,
    scd41_calls,
    bme_reads,
    proximity_reads,
    tmp119_reads,
    tmp119_init,
    tmp119_calls,
):
    class Display:
        width, height = 160, 80

        def __init__(self, **kwargs):
            pass

        def begin(self):
            pass

        def display(self, image):
            pass

    class BME280:
        def __init__(self, **kwargs):
            pass

        def update_sensor(self):
            self.temperature, self.humidity, self.pressure = next(bme_reads)

    class LTR559:
        def get_lux(self):
            return 120.0

        def get_proximity(self):
            return next(proximity_reads)

    class PMS5003:
        def __init__(self, **kwargs):
            pass

        def read(self):
            outcome = next(pms_reads)
            if isinstance(outcome, Exception):
                raise outcome
            return types.SimpleNamespace(raw_data=bytearray(outcome))

        def setup(self):
            pass

    class Scd4xDevice:
        """Each loop asks get_data_ready_status once; `scd41_reads` yields None
        (not ready) or a (co2, temp_c, rh) sample, or raises what the driver raises."""

        def __init__(self, channel):
            self._sample = None

        def stop_periodic_measurement(self):
            scd41_calls.append(("stop",))

        def start_periodic_measurement(self):
            scd41_calls.append(("start",))

        def get_data_ready_status(self):
            outcome = next(scd41_reads)
            if isinstance(outcome, Exception):
                raise outcome
            self._sample = outcome
            return outcome is not None

        def set_ambient_pressure(self, pa):
            scd41_calls.append(("pressure", pa))

        def read_measurement(self):
            return tuple(Signal(v) for v in self._sample)

    class TMP117:
        def __init__(self, bus, address):
            tmp119_calls.append(("init", address))
            outcome = next(tmp119_init)
            if isinstance(outcome, Exception):
                raise outcome

        @property
        def temperature(self):
            outcome = next(tmp119_reads)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

    module("sensirion_i2c_scd4x")
    module("sensirion_i2c_scd4x.device", Scd4xDevice=Scd4xDevice)
    module(
        "sensirion_i2c_driver",
        CrcCalculator=lambda *a: None,
        I2cConnection=lambda t: None,
        LinuxI2cTransceiver=lambda path: None,
    )
    module("sensirion_i2c_driver.errors", I2cError=I2cError)
    module("sensirion_driver_adapters")
    module("sensirion_driver_adapters.i2c_adapter")
    module("sensirion_driver_adapters.i2c_adapter.i2c_channel", I2cChannel=lambda *a, **k: None)
    module("adafruit_tmp117", TMP117=TMP117)
    module("adafruit_extended_bus", ExtendedI2C=lambda bus: None)
    module("st7735", ST7735=Display)
    module("smbus2", SMBus=lambda *a, **k: None)
    module("bme280", BME280=BME280)
    module("ltr559", LTR559=LTR559)
    module(
        "pms5003",
        PMS5003=PMS5003,
        ReadTimeoutError=ReadTimeoutError,
        ChecksumMismatchError=type("ChecksumMismatchError", (Exception,), {}),
        SerialTimeoutError=type("SerialTimeoutError", (Exception,), {}),
    )

    def read_all():
        outcome = next(gas_reads)
        if isinstance(outcome, Exception):
            raise outcome
        return types.SimpleNamespace(oxidising=45000.0, reducing=105000.0, nh3=150000.0)

    enviroplus = module("enviroplus")
    enviroplus.gas = module("enviroplus.gas", read_all=read_all)


GOOD = frame(1, 2, 3)


class Run:
    """One loop run: what reached Tier 1 and Tier 2, and what was drawn."""

    def __init__(
        self,
        tmp_path,
        monkeypatch,
        rows,
        pms_reads=None,
        gas_reads=None,
        scd41_reads=None,
        bme_reads=None,
        prepare_db=None,
        publish_s=1,
        proximity_reads=None,
        tmp119_reads=None,
        tmp119_init=None,
    ):
        self.scd41_calls, self.states, self.tmp119_calls = [], [], []
        app = tmp_path / "app"
        app.mkdir()
        for name in ("enviro_dash3.py", "enviro_screens.py", "local_sensors.py"):
            shutil.copy(REPO / name, app / name)
        self.config = json.loads((REPO / "dynamic_config.pi5.json").read_text())
        # A clock that advances a second per read: with one-second intervals
        # every read closes the previous read's interval.
        self.config["intervals"] = {"publish_s": publish_s, "display_refresh_s": 0.001}
        (app / "config.json").write_text(json.dumps(self.config))
        self.db = tmp_path / "enviro.db"
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "CREATE TABLE outdoor (ts TEXT PRIMARY KEY, tempf REAL, humidity REAL,"
                " windspeedmph REAL, windgustmph REAL, winddir REAL, uv REAL,"
                " dailyrainin REAL)"
            )
            if prepare_db:
                prepare_db(conn)
        cpu = tmp_path / "cpu_temp"
        cpu.write_text("52000")
        (app / ".env").write_text(
            f"SQLITE_PATH={self.db}\nCONFIG_PATH={app / 'config.json'}\nCPU_TEMP_PATH={cpu}\n"
        )
        for key in ("SQLITE_PATH", "CONFIG_PATH", "CPU_TEMP_PATH"):
            monkeypatch.setenv(key, "")  # registers the original for restore,
            monkeypatch.delenv(key)  # then lets the module's .env load set it

        _install_drivers(
            monkeypatch,
            pms_reads or itertools.repeat(GOOD),
            gas_reads or itertools.repeat(None),
            scd41_reads or itertools.repeat(None),
            self.scd41_calls,
            bme_reads or itertools.repeat((27.0, 50.0, 1016.0)),
            proximity_reads or itertools.repeat(0),
            tmp119_reads or itertools.repeat(24.5),
            tmp119_init or itertools.repeat(None),
            self.tmp119_calls,
        )
        monkeypatch.syspath_prepend(str(app))
        for name in ("enviro_screens", "local_sensors"):
            monkeypatch.delitem(sys.modules, name, raising=False)
        import enviro_screens

        real_render = enviro_screens.render
        monkeypatch.setattr(
            enviro_screens,
            "render",
            lambda page, state: (
                self.states.append(
                    {
                        "co2": state["co2"],
                        "co2_hist": list(state["co2_hist"]),
                        "indoor": dict(state["indoor"]),
                    }
                )
                or real_render(page, state)
            ),
        )

        # Starts at the real time, aligned to an interval: raw_retention files
        # each record under the real UTC day, so the test reads that day.
        start = int(time.time()) // 60 * 60
        self.start = datetime.fromtimestamp(start, timezone.utc)
        self.day = datetime.now(timezone.utc).date().isoformat()
        clock = itertools.count(start)
        monkeypatch.setattr(time, "time", lambda: float(next(clock)))
        since = self.start.strftime("%Y-%m-%d %H:%M:%S")

        def sleep(_seconds):
            with sqlite3.connect(self.db) as conn:
                have = (
                    conn.execute(
                        "SELECT count(*) FROM sqlite_master WHERE name='readings'"
                    ).fetchone()[0]
                    and conn.execute(
                        "SELECT count(*) FROM readings WHERE ts >= ?", (since,)
                    ).fetchone()[0]
                )
            if have >= rows:
                raise _Stop

        monkeypatch.setattr(time, "sleep", sleep)

        try:
            runpy.run_path(str(app / "enviro_dash3.py"), run_name="__main__")
        except _Stop:
            pass

    def readings(self, columns=READINGS):
        with sqlite3.connect(self.db) as conn:
            return conn.execute(f"SELECT {columns} FROM readings ORDER BY ts").fetchall()

    def tier1(self):
        from raw_retention import read_day

        return [
            (outcome, json.loads(blob))
            for _c, outcome, blob in read_day("local_sensors", self.day)
            if blob is not None
        ]


def test_failed_pm_read_is_stored_as_null_not_the_last_good_value(tmp_path, monkeypatch):
    pms = iter([GOOD, ReadTimeoutError("no frame"), ReadTimeoutError("no frame"), GOOD])
    run = Run(tmp_path, monkeypatch, rows=3, pms_reads=pms)
    assert run.readings("pm1, pm25, pm10") == [(1.0, 2.0, 3.0), (None,) * 3, (None,) * 3]


def test_sensor_error_ends_the_process(tmp_path, monkeypatch):
    gas = iter([None, OSError("i2c read failed")])
    with pytest.raises(OSError, match="i2c read failed"):
        Run(tmp_path, monkeypatch, rows=99, gas_reads=gas)


def test_tier1_keeps_every_read_as_the_driver_returned_it(tmp_path, monkeypatch):
    pms = iter([GOOD, ReadTimeoutError("no frame"), GOOD])
    scd = iter([(612, 23.871337, 47.625732), None, None])
    run = Run(tmp_path, monkeypatch, rows=2, pms_reads=pms, scd41_reads=scd)
    records = run.tier1()
    assert [outcome for outcome, _ in records] == ["ok", "partial", "ok"]
    first, second = records[0][1], records[1][1]
    assert first["bme280"] == [{"temperature": 27.0, "humidity": 50.0, "pressure": 1016.0}]
    assert first["tmp119"] == {"temperature_c": 24.5}
    assert first["pms5003_frame_hex"] == GOOD.hex()
    assert first["mics6814_ohms"] == {"oxidising": 45000.0, "reducing": 105000.0, "nh3": 150000.0}
    assert first["cpu_temp_milli_c"] == 52000
    assert first["scd41"] == {"co2_ppm": 612, "temperature_c": 23.871337, "rh": 47.625732}
    assert "pms5003_frame_hex" not in second and "no frame" in second["pms5003_error"]
    # No hand near the sensor: no tap is recorded.
    assert not any("ltr559_taps" in r for _, r in records)


def test_readings_are_derived_and_replay_reproduces_them(tmp_path, monkeypatch):
    scd = iter([(612, 23.9, 47.6), None, (640, 24.0, 48.0), None])
    run = Run(tmp_path, monkeypatch, rows=3, scd41_reads=scd)
    live = run.readings()
    # Unit definition: 24.5 C * 9/5 + 32 = 76.1 F; RH is reported SCD41 RH.
    assert live[0][1:3] == (76.1, 47.6)

    import local_sensors

    with sqlite3.connect(run.db) as conn:
        conn.execute("DELETE FROM readings")
        assert local_sensors.replay(conn, [run.start.date().isoformat()], run.config)["rows"] == 4
        replayed = conn.execute(f"SELECT {READINGS} FROM readings ORDER BY ts").fetchall()
    # Replay also closes the interval live had not closed when it stopped.
    assert replayed[:3] == live

    # Replaying on a coarser grid replaces the one-second rows; none is left
    # behind on the old grid.
    coarser = {**run.config, "intervals": {**run.config["intervals"], "publish_s": 60}}
    with sqlite3.connect(run.db) as conn:
        assert local_sensors.replay(conn, [run.start.date().isoformat()], coarser)["rows"] == 1
        assert conn.execute("SELECT ts FROM readings").fetchall() == [
            (run.start.strftime("%Y-%m-%d %H:%M:%S"),)
        ]


def test_scd41_sample_is_stored_once_as_reported_and_a_gap_is_null(tmp_path, monkeypatch):
    sample = (612, 23.871337, 47.625732)
    scd = iter([sample, None, (640, 24.0, 48.0), None])
    run = Run(tmp_path, monkeypatch, rows=3, scd41_reads=scd)
    # The interval after a sample, with none of its own, is NULL, not a repeat.
    assert run.readings("co2_ppm, scd41_temp_c, scd41_rh") == [
        sample,
        (None, None, None),
        (640, 24.0, 48.0),
    ]


def test_scd41_gets_bme280_pressure_in_pa_and_restarts_measurement(tmp_path, monkeypatch):
    run = Run(tmp_path, monkeypatch, rows=1, scd41_reads=iter([(612, 23.9, 47.6), None]))
    # BME280 stand-in reports 1016.0 hPa; the driver takes Pa.
    assert run.scd41_calls == [("stop",), ("start",), ("pressure", 101600.0)]


@pytest.mark.parametrize("error", [I2cError("nack"), OSError("nack: address ioctl")])
def test_scd41_i2c_error_is_a_failed_read_and_the_lane_restarts(tmp_path, monkeypatch, error):
    # The transceiver's address ioctl raises a plain OSError, not an I2cError.
    scd = iter([(612, 23.9, 47.6), error, (640, 24.0, 48.0), None])
    run = Run(tmp_path, monkeypatch, rows=3, scd41_reads=scd)
    assert run.readings("pm1, co2_ppm") == [(1.0, 612), (1.0, None), (1.0, 640)]
    assert [c[0] for c in run.scd41_calls if c[0] != "pressure"] == ["stop", "start"] * 2
    assert "nack" in run.tier1()[1][1]["scd41_error"]


def test_display_clears_co2_after_a_silent_interval_and_the_trend_shows_the_gap(
    tmp_path, monkeypatch
):
    scd = iter([(612, 23.9, 47.6), None, None, None])
    run = Run(tmp_path, monkeypatch, rows=3, scd41_reads=scd)
    assert [s["co2"] for s in run.states] == [612, 612, None, None]
    assert run.states[-1]["co2_hist"] == [612, None, None]
    # Room temperature is TMP119; reported SCD RH keeps its existing display rule.
    assert run.states[0]["indoor"]["temp_f"] == 76.1
    assert run.states[0]["indoor"]["humidity"] == 47.6


def test_an_existing_fifteen_column_table_keeps_its_rows_and_gains_the_new_columns(
    tmp_path, monkeypatch
):
    legacy = (
        "2026-10-20 12:00:00",
        76.5,
        51.0,
        1018.6,
        3.2,
        40.1,
        100.2,
        150.3,
        0.4,
        1.2,
        2.0,
        52.0,
        0.5,
        6000.0,
        3600,
    )

    def prepare(conn):
        conn.execute(
            "CREATE TABLE readings (ts TEXT PRIMARY KEY, temp_f REAL, humidity REAL,"
            " pressure REAL, lux REAL, oxidising REAL, reducing REAL, ammonia REAL,"
            " pm1 REAL, pm25 REAL, pm10 REAL, cpu_temp_c REAL, cpu_load REAL,"
            " mem_free_mb REAL, uptime_s INTEGER)"
        )
        conn.execute("INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", legacy)

    run = Run(
        tmp_path,
        monkeypatch,
        rows=1,
        scd41_reads=iter([(612, 23.9, 47.6), None]),
        prepare_db=prepare,
    )
    rows = run.readings()
    assert rows[0] == legacy + (None, None, None)
    assert rows[1][15:] == (612, 23.9, 47.6)


def test_an_interval_takes_each_lanes_newest_successful_read(tmp_path, monkeypatch):
    bme = itertools.cycle([(26.0, 40.0, 1015.0), (27.0, 41.0, 1016.0), (28.0, 42.0, 1017.0)])
    pms = iter([frame(1, 2, 3), frame(4, 5, 6), ReadTimeoutError("no frame")] * 3)
    scd = iter([(600, 23.0, 45.0), (610, 23.5, 46.0), None] * 3)
    tmp = iter([0.0, 5.0, OSError("TMP119 read nack")] * 3)
    run = Run(
        tmp_path,
        monkeypatch,
        rows=2,
        pms_reads=pms,
        scd41_reads=scd,
        tmp119_reads=tmp,
        bme_reads=bme,
        publish_s=3,
    )
    rows = run.readings("ts, temp_f, humidity, pressure, pm1, pm25, pm10, co2_ppm")
    assert rows[0] == (
        run.start.strftime("%Y-%m-%d %H:%M:%S"),
        41.0,
        46.0,
        1017.0,
        4.0,
        5.0,
        6.0,
        610,
    )
    # 5 C = 41 F, not the BME280's 28 C. RH46 is uncorrected SCD output.
    # Pressure uses the last BME280 read; failed TMP/PMS reads do not erase good
    # samples earlier in this same interval.


def test_replay_of_a_day_includes_its_last_reads_filed_after_midnight(tmp_path, monkeypatch):
    """raw_retention files a record under the day it was retained; a read just
    before midnight retained just after is in the next day's file."""
    import local_sensors
    import raw_retention

    cfg = json.loads((REPO / "dynamic_config.pi5.json").read_text())
    base = {
        "bme280": [{"temperature": 27.0, "humidity": 50.0, "pressure": 1016.0}] * 3,
        "cpu_temp_milli_c": 52000,
        "ltr559_lux": 120.0,
        "mics6814_ohms": {"oxidising": 45000.0, "reducing": 105000.0, "nh3": 150000.0},
        "pi": {"loadavg_1m": 0.5, "mem_available_kb": 6000000, "uptime_s": 100.0},
    }

    class Clock(datetime):
        at = None

        @classmethod
        def now(cls, tz=None):
            return cls.at

    monkeypatch.setattr(raw_retention, "datetime", Clock)
    for read, filed, co2 in (
        ("2026-10-21T23:59:58+00:00", "2026-10-21T23:59:58+00:00", 600),
        ("2026-10-21T23:59:59.900+00:00", "2026-10-22T00:00:00.100+00:00", 610),
        ("2026-10-22T00:00:01+00:00", "2026-10-22T00:00:01+00:00", 620),
    ):
        Clock.at = datetime.fromisoformat(filed)
        sample = {
            **base,
            "read_utc": read,
            "scd41": {"co2_ppm": co2, "temperature_c": 23.0, "rh": 45.0},
        }
        raw_retention.retain(local_sensors.PROVIDER, json.dumps(sample).encode())

    db = sqlite3.connect(tmp_path / "replay.db")
    local_sensors.ensure_schema(db)
    assert local_sensors.replay(db, ["2026-10-21"], cfg) == {"samples": 2, "rows": 1}
    assert db.execute("SELECT ts, co2_ppm FROM readings").fetchall() == [
        ("2026-10-21 23:59:00", 610)
    ]
    # These old retained records have no TMP119. No synthetic temperature or
    # BME fallback, while SCD RH and old multi-read BME pressure still replay.
    assert db.execute("SELECT temp_f, humidity, pressure FROM readings").fetchall() == [
        (None, 45.0, 1016.0)
    ]


def test_a_hot_reloaded_publish_interval_closes_the_open_interval_on_its_own_grid(
    tmp_path, monkeypatch
):
    """publish_s 1 -> 3 mid-run: the open one-second interval is written under
    its own key, not the coarser grid's (which would land on an earlier row)."""
    config_path = []
    calls = itertools.count()

    def bme():
        while True:
            # One BME read per loop: the third loop rewrites the config.
            if next(calls) == 2:
                cfg = json.loads(config_path[0].read_text())
                cfg["intervals"]["publish_s"] = 3
                config_path[0].write_text(json.dumps(cfg))
                os.utime(config_path[0], (time.monotonic() + 1e6, time.monotonic() + 1e6))
            yield (27.0, 50.0, 1016.0)

    original = Run.__init__

    def capture(self, *a, **k):
        app = a[0] / "app"
        config_path.append(app / "config.json")
        original(self, *a, **k)

    monkeypatch.setattr(Run, "__init__", capture)
    scd = iter([(600, 23.0, 45.0), (601, 23.0, 45.0), (602, 23.0, 45.0)] + [None] * 20)
    run = Run(tmp_path, monkeypatch, rows=4, scd41_reads=scd, bme_reads=bme())
    rows = run.readings("ts, co2_ppm")
    second = (run.start + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    # Each one-second interval keeps its own row and its own read.
    assert rows[:2] == [(run.start.strftime("%Y-%m-%d %H:%M:%S"), 600), (second, 601)]
    assert rows[3][0] == (run.start + timedelta(seconds=3)).strftime("%Y-%m-%d %H:%M:%S")
    assert len(run.tier1()) > 5  # the fourth row required the coarser interval to close


def test_a_pre_tier1_row_sharing_the_first_intervals_key_is_kept(tmp_path, monkeypatch):
    """A row from before Tier 1 has no reads to rebuild it from, so a derived
    row landing on the same ts never overwrites it."""
    start = datetime.fromtimestamp(int(time.time()) // 60 * 60, timezone.utc)
    legacy_ts = start.strftime("%Y-%m-%d %H:%M:%S")

    def prepare(conn):
        conn.execute("CREATE TABLE readings (ts TEXT PRIMARY KEY, temp_f REAL)")
        conn.execute("INSERT INTO readings VALUES (?, 99.9)", (legacy_ts,))

    run = Run(tmp_path, monkeypatch, rows=2, prepare_db=prepare)
    assert run.start == start  # the run began in the same minute
    assert run.readings("ts, temp_f")[0] == (legacy_ts, 99.9)


def test_a_read_the_canonical_tier_could_not_store_ends_the_process_underived(
    tmp_path, monkeypatch
):
    """The third read's Tier 1 append fails: the process ends (restart and
    OnFailure surface it), and no readings row is derived from that read."""
    import raw_retention

    real_fsync, appends = raw_retention.os.fsync, itertools.count()

    def fsync(fd):
        if next(appends) == 2:
            raise OSError(28, "No space left on device")
        real_fsync(fd)

    monkeypatch.setattr(raw_retention.os, "fsync", fsync)
    run = None
    with pytest.raises(raw_retention.RetentionWriteError):
        run = Run(
            tmp_path,
            monkeypatch,
            rows=99,
            scd41_reads=iter([(600, 23.0, 45.0), (601, 23.0, 45.0), (602, 23.0, 45.0)]),
        )
    assert run is None
    with sqlite3.connect(tmp_path / "enviro.db") as conn:
        # Read 1's interval was closed by read 2; read 2's would have been
        # closed by read 3, which never reached Tier 1.
        assert conn.execute("SELECT co2_ppm FROM readings").fetchall() == [(600,)]


def _retain_reads(monkeypatch, reads):
    """Retain local_sensors records with the given read times (and file them
    at those times), each carrying its co2 as a marker."""
    import local_sensors
    import raw_retention

    base = {
        "bme280": [{"temperature": 27.0, "humidity": 50.0, "pressure": 1016.0}] * 3,
        "cpu_temp_milli_c": 52000,
        "ltr559_lux": 120.0,
        "mics6814_ohms": {"oxidising": 45000.0, "reducing": 105000.0, "nh3": 150000.0},
        "pi": {"loadavg_1m": 0.5, "mem_available_kb": 6000000, "uptime_s": 100.0},
    }

    class Clock(datetime):
        at = None

        @classmethod
        def now(cls, tz=None):
            return cls.at

    with monkeypatch.context() as m:
        m.setattr(raw_retention, "datetime", Clock)
        for read, co2 in reads:
            Clock.at = datetime.fromisoformat(read)
            raw_retention.retain(
                local_sensors.PROVIDER,
                json.dumps(
                    {
                        **base,
                        "read_utc": read,
                        "scd41": {"co2_ppm": co2, "temperature_c": 23.0, "rh": 45.0},
                    }
                ).encode(),
            )


def test_replay_rewrites_each_days_first_interval_but_not_the_cutover_one(tmp_path, monkeypatch):
    import local_sensors

    cfg = json.loads((REPO / "dynamic_config.pi5.json").read_text())
    # Tier 1 begins 2026-10-21 09:00:30; the next day's first read is mid-interval.
    _retain_reads(
        monkeypatch,
        [
            ("2026-10-21T09:00:30+00:00", 500),
            ("2026-10-22T10:00:01+00:00", 600),
            ("2026-10-22T10:00:02+00:00", 601),
        ],
    )
    db = sqlite3.connect(tmp_path / "r.db")
    local_sensors.ensure_schema(db)
    # 09:55:00 stands for a row from an earlier publish_s grid, before the day's
    # first read.
    for ts in ("2026-10-21 09:00:00", "2026-10-22 09:55:00", "2026-10-22 10:00:00"):
        db.execute("INSERT INTO readings (ts, co2_ppm) VALUES (?, -1)", (ts,))
    local_sensors.replay(db, ["2026-10-21", "2026-10-22"], cfg)
    assert db.execute("SELECT ts, co2_ppm FROM readings ORDER BY ts").fetchall() == [
        # Starts before the first Tier 1 read: kept as written.
        ("2026-10-21 09:00:00", -1),
        # Starts before that day's first read, but after Tier 1 began: rebuilt.
        ("2026-10-22 10:00:00", 601),
    ]


def test_a_day_with_an_unreadable_record_fails_replay_before_any_row_changes(tmp_path, monkeypatch):
    import local_sensors

    cfg = json.loads((REPO / "dynamic_config.pi5.json").read_text())
    _retain_reads(
        monkeypatch, [("2026-10-22T10:00:01+00:00", 600), ("2026-10-22T10:01:01+00:00", 601)]
    )
    day_file = Path(os.environ["ENVIRO_RAW_ROOT"]) / "local_sensors" / "2026-10-22.ndjson"
    with day_file.open("a") as fh:
        fh.write('{"captured_utc": "2026-10-22T10:02:01+00:00", "outcome": "ok", "payl\n')
    db = sqlite3.connect(tmp_path / "r.db")
    local_sensors.ensure_schema(db)
    for ts in ("2026-10-22 10:00:00", "2026-10-22 10:01:00"):
        db.execute("INSERT INTO readings (ts, co2_ppm) VALUES (?, -1)", (ts,))
    db.commit()
    with pytest.raises(ValueError):
        local_sensors.replay(db, ["2026-10-22"], cfg)
    assert db.execute("SELECT ts, co2_ppm FROM readings ORDER BY ts").fetchall() == [
        ("2026-10-22 10:00:00", -1),
        ("2026-10-22 10:01:00", -1),
    ]


def test_each_tap_is_retained_once_with_the_reading_that_crossed_the_threshold(
    tmp_path, monkeypatch
):
    tap = json.loads((REPO / "dynamic_config.pi5.json").read_text())["display"]["tap_proximity"]
    # Two separate taps: near, held near (not a second tap), away, then a
    # reading exactly at the threshold, which counts as near.
    reads = iter([0, tap + 5, tap + 9, 0, tap] + [0] * 10_000)
    run = Run(tmp_path, monkeypatch, rows=3, proximity_reads=reads)
    taps = [t for _, r in run.tier1() for t in r.get("ltr559_taps", [])]
    assert [(t["proximity"], t["tap_proximity"]) for t in taps] == [(tap + 5, tap), (tap, tap)]


@pytest.mark.parametrize(
    "error",
    [
        OSError("address ioctl failed"),
        ValueError("No I2C device at address"),
        AttributeError("Cannot find a TMP117 or TMP119"),
    ],
)
def test_tmp119_init_failure_is_retained_and_other_lanes_continue(tmp_path, monkeypatch, error):
    run = Run(
        tmp_path,
        monkeypatch,
        rows=2,
        tmp119_init=iter([error, None]),
        scd41_reads=iter([(600, 23.0, 45.0), (610, 23.0, 46.0), None]),
    )
    assert run.readings("temp_f, humidity, pressure, co2_ppm") == [
        (None, 45.0, 1016.0, 600),
        (76.1, 46.0, 1016.0, 610),
    ]
    first = run.tier1()[0]
    assert first[0] == "partial" and "tmp119_error" in first[1]
    assert "tmp119" not in first[1]
    assert run.tmp119_calls == [("init", 0x48), ("init", 0x48)]


def test_tmp119_failed_interval_has_no_other_sensor_or_previous_value_fallback(
    tmp_path, monkeypatch
):
    # A valid SCD41 16-bit RH word converted per its published interface.
    reported_rh = 32768 * 100 / 65535
    run = Run(
        tmp_path,
        monkeypatch,
        rows=3,
        tmp119_reads=iter([24.5, OSError("read nack"), 0.0, 10.0]),
        scd41_reads=itertools.repeat((600, 30.0, reported_rh)),
    )
    assert run.readings("temp_f, humidity, pressure") == [
        (76.1, reported_rh, 1016.0),
        (None, reported_rh, 1016.0),
        (32.0, reported_rh, 1016.0),
    ]
    assert run.states[1]["indoor"]["temp_f"] is None
    assert run.states[1]["indoor"]["humidity"] == reported_rh  # reported RH, no Magnus
    assert run.tier1()[0][1]["scd41"]["rh"] == reported_rh
    assert run.tier1()[1][0] == "partial"
    assert run.tmp119_calls == [("init", 0x48), ("init", 0x48)]


def test_new_temperature_projection_preserves_driver_precision(tmp_path, monkeypatch):
    run = Run(tmp_path, monkeypatch, rows=1, tmp119_reads=itertools.repeat(24.46875))
    assert run.tier1()[0][1]["tmp119"]["temperature_c"] == 24.46875
    # Exact unit conversion of3132/128C, without a legacy BME display-rounding rule.
    assert run.readings("temp_f")[0][0] == pytest.approx(76.04375)


def test_old_bme_read_list_keeps_last_pressure_and_does_not_invent_tmp_history(
    tmp_path, monkeypatch
):
    run = Run(tmp_path, monkeypatch, rows=1)
    sample = run.tier1()[0][1]
    del sample["tmp119"]  # valid record shape before this sensor was acquired
    sample["bme280"] = [
        {"temperature": 27.0, "humidity": 50.0, "pressure": pressure}
        for pressure in (1015.01, 1015.02, 1015.03)
    ]
    import local_sensors

    row = local_sensors.derive_row([sample], 1)
    assert row["pressure"] == 1015.03
    assert row["temp_f"] is None
