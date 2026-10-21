#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        enviro_dash3.py
PATH:        ~/projects/enviroplus/enviro_dash3.py
DESCRIPTION: Enviro+ sensor loop and its 160x80 ST7735 display. Reads the
             BME280, LTR559, MICS6814 and PMS5003, writes one readings row per
             publish interval, and shows one of the enviro_screens pages.
             A hand over the LTR559 proximity sensor changes page.

CHANGELOG:
2026-10-11 15:10      Claude      [Feature] Four-page display drawn by
                                      enviro_screens (Glance, Air, Outside,
                                      Gas), changed by proximity tap. Removes
                                      the CO2 readout: no CO2 sensor is fitted,
                                      so it only ever showed "---". AQI moves to
                                      the 2024 EPA PM2.5 table.
                       Claude      [Fix] A failed PMS5003 read now records PM as
                                      NULL instead of repeating the last good
                                      values as fresh readings. SQLite write and
                                      loop errors end the process so the unit's
                                      restart/OnFailure policy sees them.
                                      Calibration re-resolves on any change to
                                      its config section, not only cal_actual_f.
2026-08-06 19:29      Claude      [Refactor] Remove the Adafruit IO MQTT
                                      publisher. Grafana replaced it as the
                                      display, so the publish path was making an
                                      authenticated external call every poll to
                                      feed a surface nobody reads, and the
                                      status dot it drove reported the health of
                                      a channel that no longer mattered. Also
                                      removes the broker, port, user and
                                      key it made mandatory at startup.
2026-04-09 14:00      Claude      [Docs] Update file header to Lexx standard
                                      format
2026-04-09 00:00      Claude      [Refactor] Phase 3 refactor: use shared
                                      services library for config and logging.
                                      Replace datetime.utcnow() with
                                      shared.utils.utc_now(). Fail-loud on MQTT
                                      creds via require(). Add PMS5003
                                      read-failure warning logging and
                                      stale-data tracking. Add EPA AQI
                                      breakpoint comment explaining regulatory
                                      constants.
2026-04-02 14:56      Claude      [Refactor] Store timestamps as UTC via
                                      datetime.utcnow() so SQLite epoch
                                      conversions are correct for Grafana.
                                      Existing EDT rows migrated via
                                      datetime(ts, '+4 hours').
2026-03-18 09:30      Claude      [Fix] Fix MQTT silent failure on DNS-delayed
                                      startup: move loop_start() before
                                      connect() so network thread always runs.
                                      Add is_connected() check + reconnect in
                                      write_mqtt() so messages aren't silently
                                      queued when connection was never
                                      established.
2026-03-16 04:00      Bryan       [Feature] Humidity correction for BME280
                                      self-heating: apply Magnus formula.
                                      Also update cal_actual_f to 75.1F per
                                      overnight hygrometer reference.
2026-03-16 03:30      Bryan       [Feature] Plot backgrounds tinted by
                                      worst-case severity: PM panel uses EPA AQI
                                      band color; VOC panel uses config
                                      thresholds (ox/rd/nh3). Dark 25% blend
                                      keeps lines readable at all severity
                                      levels.
2026-03-16 03:00      Bryan       [Refactor] Remove DB/RH labels; enlarge
                                      temp+RH to FONT_L, side-by-side. Remove
                                      pressure display. Replace right column PM
                                      bar/values with PM+VOC dual line plots.
2026-03-16 02:30      Bryan       [Feature] Replace raw PM2.5 bar with proper
                                      EPA AQI (0-500). AQI = max(PM2.5
                                      sub-index, PM10 sub-index) per EPA linear
                                      interpolation breakpoints.
2026-03-16 01:15      Bryan       [Feature] Initial implementation, AQM-345
                                      inspired layout. CO2 is placeholder (---)
                                      until SCD-41 connected.
2026-03-16 00:00      Bryan       [Feature] Pi 5 port: move all
                                      hardware-specific values to config/env.
                                      Display SPI/GPIO, I2C bus, BME280 addr,
                                      PMS5003 serial device, and CPU temp path
                                      are now read from dynamic_config.json
                                      ["hardware"] and .env.
--------------------------------------------------------------------------------
"""

import json
import math
import os
import sqlite3
import sys
import time
from collections import deque
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, "/home/pistrommy/projects")

import bme280
import smbus2
import st7735
from enviroplus import gas
from ltr559 import LTR559
from pms5003 import PMS5003, ChecksumMismatchError, ReadTimeoutError, SerialTimeoutError
from shared.config_service import load_env, require
from shared.db_service import connect
from shared.logging_service import setup_logger
from shared.utils import utc_now

import enviro_screens as screens

# ── Paths ──────────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_BASE, ".env")
LOG_PATH = os.path.join(_BASE, "enviro_dash.log")

load_env(_ENV_PATH, expect_key="SQLITE_PATH")

# Read after load_env, not before: consuming a key before the file that supplies
# it is loaded silently pins the default, so a change in .env would move the
# collectors to a new database while this service kept writing the old one.
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(_BASE, "enviro.db"))

CONFIG_PATH = require("CONFIG_PATH")

# ── Logging ────────────────────────────────────────────────────────────────────
log = setup_logger("enviro_dash", LOG_PATH)

# ── Dynamic config ─────────────────────────────────────────────────────────────
_config_mtime = 0.0


def load_config():
    global _config_mtime
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    _config_mtime = os.path.getmtime(CONFIG_PATH)
    return cfg


cfg = load_config()


def _r(x, n):
    """Round only real values; None (absent/failed lane) passes through as NULL."""
    return None if x is None else round(x, n)


def _round_readings(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
    """Single source of truth for sensor rounding, used by the SQLite write path."""
    return {
        "temperature": _r(temp_f, 1),
        "humidity": _r(hum, 1),
        "pressure": _r(pres, 2),
        "light": _r(lux, 1),
        "oxidising": _r(ox, 1),
        "reducing": _r(rd, 1),
        "ammonia": _r(nh3, 1),
        "pm1": _r(pm1, 1),
        "pm25": _r(pm25, 1),
        "pm10": _r(pm10, 1),
    }


# ── SQLite ─────────────────────────────────────────────────────────────────────
# Uses the shared connector rather than a private sqlite3.connect: this was a
# second implementation of the same thing, and it silently missed the busy
# timeout the other three writers get. Four processes share this database, so
# the writer without a timeout is the one that drops rows under contention.
_db = connect(SQLITE_PATH)
_db.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        ts          TEXT PRIMARY KEY,
        temp_f      REAL, humidity REAL, pressure REAL, lux REAL,
        oxidising   REAL, reducing REAL, ammonia  REAL,
        pm1         REAL, pm25     REAL, pm10     REAL,
        cpu_temp_c  REAL, cpu_load REAL, mem_free_mb REAL, uptime_s INTEGER
    )
""")
for col, typedef in [
    ("cpu_temp_c", "REAL"),
    ("cpu_load", "REAL"),
    ("mem_free_mb", "REAL"),
    ("uptime_s", "INTEGER"),
]:
    try:
        _db.execute(f"ALTER TABLE readings ADD COLUMN {col} {typedef}")
    except sqlite3.OperationalError:
        pass
_db.commit()


def _pi_telemetry():
    cpu_temp = _cpu_temp()
    with open("/proc/loadavg") as f:
        cpu_load = float(f.read().split()[0])
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable"):
                mem_free_mb = int(line.split()[1]) / 1024
                break
    with open("/proc/uptime") as f:
        uptime_s = int(float(f.read().split()[0]))
    return cpu_temp, cpu_load, mem_free_mb, uptime_s


def write_sqlite(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
    r = _round_readings(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10)
    cpu_temp, cpu_load, mem_free_mb, uptime_s = _pi_telemetry()
    _db.execute(
        "INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            utc_now(),
            r["temperature"],
            r["humidity"],
            r["pressure"],
            r["light"],
            r["oxidising"],
            r["reducing"],
            r["ammonia"],
            r["pm1"],
            r["pm25"],
            r["pm10"],
            round(cpu_temp, 1),
            round(cpu_load, 2),
            round(mem_free_mb, 1),
            uptime_s,
        ),
    )
    _db.commit()
    log.info("SQLite row written")


# ── Display ────────────────────────────────────────────────────────────────────
_hw = cfg["hardware"]
disp = st7735.ST7735(
    port=_hw["spi_port"],
    cs=_hw["spi_cs"],
    dc=_hw["display_dc"],
    backlight=_hw["display_backlight"],
    rotation=_hw["display_rotation"],
    spi_speed_hz=_hw["spi_speed_hz"],
)
disp.begin()
W, H = disp.width, disp.height  # 160 × 80

# ── Sensors ────────────────────────────────────────────────────────────────────
_i2c_bus = int(os.environ.get("I2C_BUS", 1))
_pms_device = os.environ.get("PMS5003_DEVICE", "/dev/ttyAMA0")
_cpu_temp_path = os.environ.get("CPU_TEMP_PATH", "/sys/class/thermal/thermal_zone0/temp")
_bus = smbus2.SMBus(_i2c_bus)
_bme_addr = _hw["bme280_addr"]
_bme_sensor = bme280.BME280(i2c_addr=_bme_addr, i2c_dev=_bus)
ltr559_sensor = LTR559()
pms5003_sensor = PMS5003(device=_pms_device)

# ── CPU temp compensation ──────────────────────────────────────────────────────
_cpu_hist = deque(
    [45.0] * cfg["calibration"]["cpu_hist_size"], maxlen=cfg["calibration"]["cpu_hist_size"]
)
CPU_FACTOR = 0.0


def c2f(c):
    return c * 9 / 5 + 32


def f2c(f):
    return (f - 32) * 5 / 9


def _cpu_temp():
    with open(_cpu_temp_path) as f:
        return int(f.read()) / 1000.0


def _bme_sample():
    _bme_sensor.update_sensor()
    return SimpleNamespace(
        temperature=_bme_sensor.temperature,
        humidity=_bme_sensor.humidity,
        pressure=_bme_sensor.pressure,
    )


def _calibrate(cal_actual_f):
    """Resolve the compensation model. Explicit precedence, one model only.

    The offset model (self_heat_offset_c) SUPERSEDES the proportional model. When it
    is declared, CPU_FACTOR is forced inert so a leftover `cal_actual_f` cannot
    silently derive a competing factor -- which is exactly what happened on the
    2026-07-30 changeover and was caught by the read_temp_c conflict guard.
    """
    global CPU_FACTOR
    offset_c = cfg["calibration"].get("self_heat_offset_c")
    override = cfg["calibration"].get("cpu_factor_override")
    if offset_c is not None:
        if override is not None:
            raise RuntimeError(
                "calibration declares BOTH self_heat_offset_c and"
                " cpu_factor_override; these are different compensation models."
                " Set exactly one."
            )
        CPU_FACTOR = 0.0
        log.info("compensation: constant offset %.3f C (proportional model inert)", float(offset_c))
        return
    if override is not None:
        CPU_FACTOR = float(override)
        log.info("CPU_FACTOR=%.4f (override from config)", CPU_FACTOR)
        return
    if not cal_actual_f:
        CPU_FACTOR = 0.0
        return
    cal_actual_c = f2c(cal_actual_f)
    cal_raw_c = sum(_bme_sample().temperature for _ in range(10)) / 10
    cal_cpu_c = sum(_cpu_temp() for _ in range(10)) / 10
    denom = cal_raw_c - cal_actual_c
    CPU_FACTOR = (cal_cpu_c - cal_raw_c) / denom if denom else 0.0
    log.info(
        "CPU_FACTOR=%.2f  raw=%.1f°F  cpu=%.1f°C  actual=%s°F",
        CPU_FACTOR,
        c2f(cal_raw_c),
        cal_cpu_c,
        cal_actual_f,
    )


_calibrate(cfg["calibration"]["cal_actual_f"])


def read_temp_c():
    """Returns (compensated_c, raw_chip_c). raw_chip_c is used for RH correction.

    Self-heating on this Pi 5 + M.2-spaced mounting is a near-CONSTANT pedestal,
    not a CPU-load-proportional term: measured alpha = 0.015 contributes 0.57 F
    across the full natural CPU-gap range (7-28 C), which is below the chip's own
    1.87 F short-timescale wander. The proportional `CPU_FACTOR` form is therefore
    structurally wrong here -- tuning it to be right at one gap makes it wrong by
    up to +18.8 F at another (measured). Constant offset is the correct shape.

    `cpu_factor_override` is retained ONLY as an escape hatch for hardware whose
    sensor sits directly above the SoC (the pre-M.2 geometry); when set it wins
    and the offset is ignored, fail-loud on both being set.
    """
    n = cfg["calibration"]["bme_samples"]
    raw = sum(_bme_sample().temperature for _ in range(n)) / n
    cpu = _cpu_temp()
    _cpu_hist.append(cpu)
    avg_cpu = sum(_cpu_hist) / len(_cpu_hist)

    offset_c = cfg["calibration"].get("self_heat_offset_c")
    if CPU_FACTOR:
        comp = raw - ((avg_cpu - raw) / CPU_FACTOR)
    elif offset_c is not None:
        comp = raw - float(offset_c)
    else:
        comp = raw
    return comp, raw


def correct_humidity(rh, raw_c, actual_c):
    """Correct BME280 RH for chip self-heating using the Magnus formula.
    rh      — raw sensor reading (%)
    raw_c   — BME280 chip temperature (°C), elevated by Pi CPU heat
    actual_c — compensated room temperature (°C)
    """

    def psat(t):
        return math.exp(17.625 * t / (243.04 + t))

    return min(rh * psat(raw_c) / psat(actual_c), 100.0)


# ── Trend history ──────────────────────────────────────────────────────────────
# One sample per pixel of the widest trend line (Air page, 108 px).
TREND_POINTS = 108
pm_hist = {k: deque(maxlen=TREND_POINTS) for k in ("pm1", "pm25", "pm10")}
gas_hist = {k: deque(maxlen=TREND_POINTS) for k in ("oxidising", "reducing", "ammonia")}


# ── Outdoor (Ambient station rows written by ambient_wx.py) ────────────────────
def read_outdoor():
    """Latest Ambient row plus temperature/wind history from this database.

    The latest row is returned only while it is fresher than
    display.outdoor_stale_s; an older one is None so the screen shows "--"
    rather than presenting a stale reading as current. History is drawn as is.
    """
    rows = _db.execute(
        "SELECT ts, tempf, humidity, windspeedmph, windgustmph, winddir, uv, dailyrainin"
        " FROM outdoor ORDER BY ts DESC LIMIT ?",
        (TREND_POINTS,),
    ).fetchall()
    rows = [
        dict(
            zip(
                (
                    "ts",
                    "tempf",
                    "humidity",
                    "windspeedmph",
                    "windgustmph",
                    "winddir",
                    "uv",
                    "dailyrainin",
                ),
                r,
            )
        )
        for r in reversed(rows)
    ]
    latest = rows[-1] if rows else None
    if latest is not None:
        observed = datetime.strptime(latest["ts"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        age_s = (datetime.now(timezone.utc) - observed).total_seconds()
        if age_s > cfg["display"]["outdoor_stale_s"]:
            latest = None
    return latest, [r["tempf"] for r in rows], [r["windspeedmph"] for r in rows]


# ── Page selection by proximity tap ────────────────────────────────────────────
# The ltr559 driver sets PS_MEAS_RATE to 100 ms; polling faster rereads the
# same measurement.
PROXIMITY_MEAS_S = 0.1


def wait_for_next_frame(page, near):
    """Sleep until the next display refresh, watching the LTR559 proximity
    channel. A hand moving close (rising edge past display.tap_proximity)
    advances the page and redraws at once. Returns (page, near)."""
    d = cfg["display"]
    deadline = time.monotonic() + cfg["intervals"]["display_refresh_s"]
    while time.monotonic() < deadline:
        now_near = ltr559_sensor.get_proximity() >= d["tap_proximity"]
        if now_near and not near:
            page = (page + 1) % len(screens.PAGES)
            disp.display(screens.render(page, state))
        near = now_near
        time.sleep(PROXIMITY_MEAS_S)
    return page, near


# ── Main loop ─────────────────────────────────────────────────────────────────
# Any error outside the PMS5003 lane ends the process: the unit's restart policy
# retries it, and repeated failure reaches OnFailure. A loop that logged and
# carried on kept the service "active" while the screen froze on its last frame.
pm1 = pm25 = pm10 = None  # absent/failed lane => NULL, never a fabricated zero
page, near = 0, False
_last_publish = time.time()

log.info("Enviro+ dash v3 starting")

try:
    while True:
        if os.path.getmtime(CONFIG_PATH) != _config_mtime:
            old_cal = cfg["calibration"]
            cfg = load_config()
            log.info("config reloaded: %s", CONFIG_PATH)
            new_size = cfg["calibration"]["cpu_hist_size"]
            if new_size != old_cal["cpu_hist_size"]:
                _cpu_hist.__init__(list(_cpu_hist)[-new_size:], maxlen=new_size)
            if cfg["calibration"] != old_cal:
                _calibrate(cfg["calibration"]["cal_actual_f"])

        temp_c, raw_c = read_temp_c()
        _sample = _bme_sample()
        hum = correct_humidity(_sample.humidity, raw_c, temp_c)
        pres = _sample.pressure
        lux = ltr559_sensor.get_lux()

        g = gas.read_all()
        ox = g.oxidising / 1000
        rd = g.reducing / 1000
        nh3 = g.nh3 / 1000

        try:
            p = pms5003_sensor.read()
            pm1 = float(p.pm_ug_per_m3(1.0))
            pm25 = float(p.pm_ug_per_m3(2.5))
            pm10 = float(p.pm_ug_per_m3(10))
        except (ReadTimeoutError, SerialTimeoutError, ChecksumMismatchError) as e:
            # A failed read is absent data, not the previous reading again.
            pm1 = pm25 = pm10 = None
            log.warning("PMS5003 read failed: %s — reinitializing", e)
            try:
                pms5003_sensor.setup()  # reinit serial without re-claiming GPIO
            except Exception as reinit_err:
                log.warning("PMS5003 reinit failed: %s", reinit_err)

        tf = c2f(temp_c)
        for key, value in (("pm1", pm1), ("pm25", pm25), ("pm10", pm10)):
            pm_hist[key].append(value)
        for key, value in (("oxidising", ox), ("reducing", rd), ("ammonia", nh3)):
            gas_hist[key].append(value)
        outdoor, outdoor_temps, winds = read_outdoor()

        state = {
            "indoor": {"temp_f": tf, "humidity": hum, "pressure": pres},
            "pm": {"pm1": pm1, "pm25": pm25, "pm10": pm10},
            "pm_hist": pm_hist,
            "gas": {"oxidising": ox, "reducing": rd, "ammonia": nh3},
            "gas_hist": gas_hist,
            "outdoor": outdoor,
            "outdoor_temp_hist": outdoor_temps,
            "wind_hist": winds,
            "thresholds": cfg["thresholds"],
        }
        disp.display(screens.render(page, state))

        now = time.time()
        if now - _last_publish >= cfg["intervals"]["publish_s"]:
            write_sqlite(tf, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10)
            _last_publish = now

        page, near = wait_for_next_frame(page, near)
except KeyboardInterrupt:
    log.info("Stopped by user")
