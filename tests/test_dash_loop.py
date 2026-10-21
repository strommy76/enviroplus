"""
--------------------------------------------------------------------------------
FILE:        test_dash_loop.py
PATH:        ~/projects/enviroplus/tests/test_dash_loop.py
DESCRIPTION: Runs the real enviro_dash3.py loop against a temporary database
             with the hardware drivers replaced by stand-ins that return what
             the real drivers return (or raise what they raise), and checks
             what reaches the readings table.

CHANGELOG:
2026-10-20 22:10      Claude      [Feature] SCD41 samples stored as the driver
                                      reports them, once each; an interval with
                                      no new sample stores NULL.
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
import sys
import time
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


class _Stop(BaseException):
    """Ends the loop from the sleep stand-in without looking like an error."""


class ReadTimeoutError(Exception):
    pass


class Signal:
    """What the Sensirion driver's read_measurement returns: objects whose
    .value is the converted reading."""

    def __init__(self, value):
        self.value = value


def _install_drivers(monkeypatch, pms_reads, gas_reads, scd41_reads, scd41_calls):
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
            self.temperature, self.humidity, self.pressure = 27.0, 50.0, 1016.0

    class LTR559:
        def get_lux(self):
            return 120.0

        def get_proximity(self):
            return 0

    class Frame:
        def __init__(self, values):
            self.values = values

        def pm_ug_per_m3(self, size):
            return self.values[size]

    class PMS5003:
        def __init__(self, **kwargs):
            pass

        def read(self):
            outcome = next(pms_reads)
            if isinstance(outcome, Exception):
                raise outcome
            return Frame(outcome)

        def setup(self):
            pass

    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

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

    module("sensirion_i2c_scd4x")
    module("sensirion_i2c_scd4x.device", Scd4xDevice=Scd4xDevice)
    module("sensirion_i2c_driver", CrcCalculator=lambda *a: None,
           I2cConnection=lambda t: None, LinuxI2cTransceiver=lambda path: None)
    module("sensirion_driver_adapters")
    module("sensirion_driver_adapters.i2c_adapter")
    module("sensirion_driver_adapters.i2c_adapter.i2c_channel",
           I2cChannel=lambda *a, **k: None)
    module("st7735", ST7735=Display)
    module("smbus2", SMBus=lambda *a, **k: None)
    module("bme280", BME280=BME280)
    module("ltr559", LTR559=LTR559)
    module("pms5003", PMS5003=PMS5003, ReadTimeoutError=ReadTimeoutError,
           ChecksumMismatchError=type("ChecksumMismatchError", (Exception,), {}),
           SerialTimeoutError=type("SerialTimeoutError", (Exception,), {}))

    def read_all():
        outcome = next(gas_reads)
        if isinstance(outcome, Exception):
            raise outcome
        return types.SimpleNamespace(oxidising=45000, reducing=105000, nh3=150000)

    enviroplus = module("enviroplus")
    enviroplus.gas = module("enviroplus.gas", read_all=read_all)


def _run(tmp_path, monkeypatch, pms_reads, gas_reads, loops,
         scd41_reads=None, scd41_calls=None, columns="pm1, pm25, pm10"):
    if scd41_reads is None:
        scd41_reads = itertools.repeat(None)
    if scd41_calls is None:
        scd41_calls = []
    app = tmp_path / "app"
    app.mkdir()
    for name in ("enviro_dash3.py", "enviro_screens.py"):
        shutil.copy(REPO / name, app / name)
    config = json.loads((REPO / "dynamic_config.pi5.json").read_text())
    config["intervals"] = {"publish_s": 0, "display_refresh_s": 0.001}
    (app / "config.json").write_text(json.dumps(config))
    db = tmp_path / "enviro.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE outdoor (ts TEXT PRIMARY KEY, tempf REAL, humidity REAL,"
                     " windspeedmph REAL, windgustmph REAL, winddir REAL, uv REAL,"
                     " dailyrainin REAL)")
    cpu = tmp_path / "cpu_temp"
    cpu.write_text("52000")
    (app / ".env").write_text(f"SQLITE_PATH={db}\nCONFIG_PATH={app / 'config.json'}\n"
                              f"CPU_TEMP_PATH={cpu}\n")
    for key in ("SQLITE_PATH", "CONFIG_PATH", "CPU_TEMP_PATH"):
        monkeypatch.setenv(key, "")   # registers the original for restore,
        monkeypatch.delenv(key)       # then lets the module's .env load set it

    _install_drivers(monkeypatch, pms_reads, gas_reads, scd41_reads, scd41_calls)
    monkeypatch.syspath_prepend(str(app))
    monkeypatch.delitem(sys.modules, "enviro_screens", raising=False)

    # readings.ts is second-resolution; give each publish its own second.
    clock = (f"2026-10-11 12:00:{s:02d}" for s in itertools.count())
    import shared.utils
    monkeypatch.setattr(shared.utils, "utc_now", lambda: next(clock))

    published = []
    real_commit = sqlite3.Connection.commit

    def sleep(_seconds):
        if len(published) >= loops:
            raise _Stop
    monkeypatch.setattr(time, "sleep", sleep)

    import shared.db_service
    real_connect = shared.db_service.connect

    def connect(path):
        conn = real_connect(path)

        class Counting:
            def __getattr__(self, name):
                return getattr(conn, name)

            def commit(self):
                real_commit(conn)
                published.append(True)
        return Counting()
    monkeypatch.setattr(shared.db_service, "connect", connect)

    try:
        runpy.run_path(str(app / "enviro_dash3.py"), run_name="__main__")
    except _Stop:
        pass
    with sqlite3.connect(db) as conn:
        return conn.execute(f"SELECT {columns} FROM readings ORDER BY ts").fetchall()


def test_failed_pm_read_is_stored_as_null_not_the_last_good_value(tmp_path, monkeypatch):
    good = {1.0: 0.4, 2.5: 1.2, 10: 2.0}
    pms = iter([good, ReadTimeoutError("no frame"), ReadTimeoutError("no frame")])
    gas = itertools.repeat(None)
    rows = _run(tmp_path, monkeypatch, pms, gas, loops=4)  # schema commit + 3 rows
    assert rows == [(0.4, 1.2, 2.0), (None, None, None), (None, None, None)]


def test_sensor_error_ends_the_process(tmp_path, monkeypatch):
    good = {1.0: 0.4, 2.5: 1.2, 10: 2.0}
    pms = itertools.repeat(good)
    gas = iter([None, OSError("i2c read failed")])
    with pytest.raises(OSError, match="i2c read failed"):
        _run(tmp_path, monkeypatch, pms, gas, loops=99)


SCD41_COLUMNS = "co2_ppm, scd41_temp_c, scd41_rh"


def test_scd41_sample_is_stored_once_as_reported_and_a_gap_is_null(tmp_path, monkeypatch):
    sample = (612, 23.871337, 47.625732)
    scd = iter([sample, None, (640, 24.0, 48.0)])
    pms = itertools.repeat({1.0: 0.4, 2.5: 1.2, 10: 2.0})
    rows = _run(tmp_path, monkeypatch, pms, itertools.repeat(None), loops=4,
                scd41_reads=scd, columns=SCD41_COLUMNS)
    # The interval after a sample, with none of its own, is NULL, not a repeat.
    assert rows == [sample, (None, None, None), (640, 24.0, 48.0)]


def test_scd41_gets_bme280_pressure_in_pa_and_restarts_measurement(tmp_path, monkeypatch):
    calls = []
    scd = iter([(612, 23.9, 47.6), None])
    pms = itertools.repeat({1.0: 0.4, 2.5: 1.2, 10: 2.0})
    _run(tmp_path, monkeypatch, pms, itertools.repeat(None), loops=3,
         scd41_reads=scd, scd41_calls=calls)
    # BME280 stand-in reports 1016.0 hPa; the driver takes Pa.
    assert calls == [("stop",), ("start",), ("pressure", 101600.0)]


def test_scd41_error_ends_the_process(tmp_path, monkeypatch):
    scd = iter([(612, 23.9, 47.6), OSError("scd41 nack")])
    pms = itertools.repeat({1.0: 0.4, 2.5: 1.2, 10: 2.0})
    with pytest.raises(OSError, match="scd41 nack"):
        _run(tmp_path, monkeypatch, pms, itertools.repeat(None), loops=99, scd41_reads=scd)
