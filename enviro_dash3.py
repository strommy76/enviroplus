#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        enviro_dash3.py
PATH:        ~/projects/enviroplus/enviro_dash3.py
DESCRIPTION: Enviro+ sensor loop and its 160x80 ST7735 display. Reads the
             BME280, LTR559, MICS6814, PMS5003 and SCD41, writes one readings
             row per publish interval, and shows one of the enviro_screens
             pages. A hand over the LTR559 proximity sensor changes page.

CHANGELOG:
2026-10-20 22:30      Claude      [Feature] Every sensor read is retained in
                                      Tier 1 (raw_retention provider
                                      "local_sensors") as each driver returned
                                      it; `readings` becomes Tier 2, derived
                                      by local_sensors.derive_row, the same
                                      projection --replay uses. Adds the SCD41
                                      (Sensirion driver, I2C 0x62): CO2, its
                                      temperature and RH, a CO2 page, and the
                                      indoor temperature/RH on screen. An SCD41
                                      I2C error is that lane's failed read, not
                                      the process's. Removes the startup-derived
                                      proportional CPU-factor model: it is inert
                                      under self_heat_offset_c and could not be
                                      rebuilt from retained reads.
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
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone

sys.path.insert(0, "/home/pistrommy/projects")

import bme280
import smbus2
import st7735
from enviroplus import gas
from ltr559 import LTR559
from pms5003 import PMS5003, ChecksumMismatchError, ReadTimeoutError, SerialTimeoutError
from sensirion_driver_adapters.i2c_adapter.i2c_channel import I2cChannel
from sensirion_i2c_driver import CrcCalculator, I2cConnection, LinuxI2cTransceiver
from sensirion_i2c_scd4x.device import Scd4xDevice

from shared.config_service import load_env, require
from shared.db_service import connect
from shared.logging_service import setup_logger
from raw_retention import OUTCOME_OK, OUTCOME_PARTIAL, retain
from raw_retention import configure as configure_retention

import enviro_screens as screens
import local_sensors

# ── Paths ──────────────────────────────────────────────────────────────────────
_BASE       = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH   = os.path.join(_BASE, ".env")
LOG_PATH    = os.path.join(_BASE, "enviro_dash.log")

load_env(_ENV_PATH, expect_key="SQLITE_PATH")

# Read after load_env, not before: consuming a key before the file that supplies
# it is loaded silently pins the default, so a change in .env would move the
# collectors to a new database while this service kept writing the old one.
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(_BASE, "enviro.db"))

CONFIG_PATH = require("CONFIG_PATH")
configure_retention(os.environ.get("ENVIRO_RAW_ROOT", os.path.join(_BASE, "raw-capture")))

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

# ── SQLite (Tier 2) ────────────────────────────────────────────────────────────
# Uses the shared connector rather than a private sqlite3.connect: this was a
# second implementation of the same thing, and it silently missed the busy
# timeout the other three writers get. Four processes share this database, so
# the writer without a timeout is the one that drops rows under contention.
_db = connect(SQLITE_PATH)
local_sensors.ensure_schema(_db)

# ── Display ────────────────────────────────────────────────────────────────────
_hw = cfg["hardware"]
disp = st7735.ST7735(port=_hw["spi_port"], cs=_hw["spi_cs"],
                     dc=_hw["display_dc"], backlight=_hw["display_backlight"],
                     rotation=_hw["display_rotation"],
                     spi_speed_hz=_hw["spi_speed_hz"])
disp.begin()
W, H = disp.width, disp.height  # 160 × 80

# ── Sensors ────────────────────────────────────────────────────────────────────
_i2c_bus       = int(os.environ.get("I2C_BUS", 1))
_pms_device    = os.environ.get("PMS5003_DEVICE", "/dev/ttyAMA0")
_cpu_temp_path = os.environ.get("CPU_TEMP_PATH", "/sys/class/thermal/thermal_zone0/temp")
_bus           = smbus2.SMBus(_i2c_bus)
_bme_addr      = _hw["bme280_addr"]
_bme_sensor    = bme280.BME280(i2c_addr=_bme_addr, i2c_dev=_bus)
ltr559_sensor  = LTR559()
pms5003_sensor = PMS5003(device=_pms_device)

# SCD41 shares the I2C bus; 0x62 is fixed in the part. Sensirion's CRC-8
# parameters (poly 0x31, init 0xFF) are from its datasheet and driver examples.
SCD41_ADDR = 0x62
scd41_sensor = Scd4xDevice(I2cChannel(
    I2cConnection(LinuxI2cTransceiver(f"/dev/i2c-{_i2c_bus}")),
    slave_address=SCD41_ADDR, crc=CrcCalculator(8, 0x31, 0xFF, 0x0)))
_scd41_measuring = False


def _scd41_start():
    """(Re)start periodic measurement, one sample per 5 s. A previous process
    may have left it running, and the part takes no other command until it
    stops; the driver waits out the stop itself. Called again on the next read
    after a failure, so a breakout reconnected later resumes."""
    global _scd41_measuring
    scd41_sensor.stop_periodic_measurement()
    scd41_sensor.start_periodic_measurement()
    _scd41_measuring = True


def _utc_iso():
    return datetime.fromtimestamp(time.time(), timezone.utc).isoformat()


def _pi_raw():
    with open("/proc/loadavg") as f:
        loadavg_1m = float(f.read().split()[0])
    with open("/proc/meminfo") as f:
        mem_available_kb = next(int(line.split()[1]) for line in f
                                if line.startswith("MemAvailable"))
    with open("/proc/uptime") as f:
        uptime_s = float(f.read().split()[0])
    return {"loadavg_1m": loadavg_1m, "mem_available_kb": mem_available_kb,
            "uptime_s": uptime_s}


def read_sample():
    """One loop's reads, each as its driver returned it: the Tier 1 record.

    PMS5003 and SCD41 are cabled peripherals: a failed read is that lane's
    recorded error, and the other lanes are still recorded. A failure in the
    HAT's own sensors (BME280, LTR559, MICS6814) ends the process, so the
    unit's restart/OnFailure policy reports it."""
    sample = {"read_utc": _utc_iso()}
    sample["bme280"] = []
    for _ in range(cfg["calibration"]["bme_samples"]):
        _bme_sensor.update_sensor()
        sample["bme280"].append({"temperature": _bme_sensor.temperature,
                                 "humidity": _bme_sensor.humidity,
                                 "pressure": _bme_sensor.pressure})
    with open(_cpu_temp_path) as f:
        sample["cpu_temp_milli_c"] = int(f.read())
    sample["ltr559_lux"] = ltr559_sensor.get_lux()
    # Proximity drives page taps only, so Tier 1 keeps the taps (operator,
    # 2026-10-20 23:11): each with the reading that crossed the threshold.
    if _tap_events:
        sample["ltr559_taps"] = _tap_events[:]
        _tap_events.clear()
    g = gas.read_all()
    sample["mics6814_ohms"] = {"oxidising": g.oxidising, "reducing": g.reducing, "nh3": g.nh3}
    sample["pi"] = _pi_raw()

    try:
        sample["pms5003_frame_hex"] = bytes(pms5003_sensor.read().raw_data).hex()
    except (ReadTimeoutError, SerialTimeoutError, ChecksumMismatchError) as e:
        sample["pms5003_error"] = repr(e)
        log.warning("PMS5003 read failed: %s — reinitializing", e)
        try:
            pms5003_sensor.setup()  # reinit serial without re-claiming GPIO
        except Exception as reinit_err:
            log.warning("PMS5003 reinit failed: %s", reinit_err)

    global _scd41_measuring
    try:
        if not _scd41_measuring:
            _scd41_start()
        if scd41_sensor.get_data_ready_status():
            # Sensirion recommends continuous pressure compensation; it applies
            # to the next sample. BME280 reports hPa, the driver takes Pa.
            scd41_sensor.set_ambient_pressure(sample["bme280"][-1]["pressure"] * 100)
            co2, scd_t, scd_rh = scd41_sensor.read_measurement()
            sample["scd41"] = {"co2_ppm": co2.value, "temperature_c": scd_t.value,
                               "rh": scd_rh.value}
    except OSError as e:
        # I2cError subclasses OSError; the transceiver's own address ioctl
        # raises a plain OSError. Either is this lane's failed read.
        _scd41_measuring = False
        sample["scd41_error"] = repr(e)
        log.warning("SCD41 read failed: %s", e)
    return sample


def retain_sample(sample):
    """Write the record to Tier 1. A failed lane makes the record partial. A
    record the store could not keep raises RetentionWriteError, which ends the
    process before anything is derived from it."""
    failed = sorted(k[:-len("_error")] for k in sample if k.endswith("_error"))
    retain(local_sensors.PROVIDER, json.dumps(sample, separators=(",", ":")).encode(),
           outcome=OUTCOME_PARTIAL if failed else OUTCOME_OK,
           detail=("failed: " + ", ".join(failed)) if failed else None)


# ── Trend history ──────────────────────────────────────────────────────────────
# One sample per pixel of the widest trend line (Air page, 108 px).
TREND_POINTS = 108
pm_hist  = {k: deque(maxlen=TREND_POINTS) for k in ("pm1", "pm25", "pm10")}
gas_hist = {k: deque(maxlen=TREND_POINTS) for k in ("oxidising", "reducing", "ammonia")}
co2_hist = deque(maxlen=TREND_POINTS)   # one point per publish interval


# ── Outdoor (Ambient station rows written by ambient_wx.py) ────────────────────
def read_outdoor():
    """Latest Ambient row plus temperature/wind history from this database.

    The latest row is returned only while it is fresher than
    display.outdoor_stale_s; an older one is None so the screen shows "--"
    rather than presenting a stale reading as current. History is drawn as is.
    """
    rows = _db.execute(
        "SELECT ts, tempf, humidity, windspeedmph, windgustmph, winddir, uv, dailyrainin"
        " FROM outdoor ORDER BY ts DESC LIMIT ?", (TREND_POINTS,)
    ).fetchall()
    rows = [dict(zip(("ts", "tempf", "humidity", "windspeedmph", "windgustmph",
                      "winddir", "uv", "dailyrainin"), r)) for r in reversed(rows)]
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


# Taps seen while waiting for the next frame; the next Tier 1 record carries
# them. A tap is a rising edge past display.tap_proximity.
_tap_events = []


def wait_for_next_frame(page, near):
    """Sleep until the next display refresh, watching the LTR559 proximity
    channel. A hand moving close (rising edge past display.tap_proximity)
    advances the page and redraws at once. Returns (page, near)."""
    d = cfg["display"]
    deadline = time.monotonic() + cfg["intervals"]["display_refresh_s"]
    while time.monotonic() < deadline:
        proximity = ltr559_sensor.get_proximity()
        now_near = proximity >= d["tap_proximity"]
        if now_near and not near:
            _tap_events.append({"read_utc": _utc_iso(), "proximity": proximity,
                                "tap_proximity": d["tap_proximity"]})
            page = (page + 1) % len(screens.PAGES)
            disp.display(screens.render(page, state))
        near = now_near
        time.sleep(PROXIMITY_MEAS_S)
    return page, near


# ── Main loop ─────────────────────────────────────────────────────────────────
# Every read reaches Tier 1 first. When a read opens a new publish interval, the
# finished interval's records become one `readings` row through derive_row, the
# projection --replay uses. Any error outside the cabled lanes ends the process:
# the unit's restart policy retries it, and repeated failure reaches OnFailure.
page, near = 0, False
# pending: the open interval's records; pending_s: the publish_s grid that
# opened it. A hot-reloaded publish_s changes the bucket numbering, so the open
# interval closes, and it is keyed on its own grid.
interval, pending, pending_s = None, [], None
# The SCD41 values on screen: the newest sample, cleared when a whole publish
# interval passes without one.
scd41_shown = None

log.info("Enviro+ dash v3 starting")

try:
    while True:
        if os.path.getmtime(CONFIG_PATH) != _config_mtime:
            cfg = load_config()
            log.info("config reloaded: %s", CONFIG_PATH)

        sample = read_sample()
        retain_sample(sample)

        publish_s = cfg["intervals"]["publish_s"]
        b = local_sensors.bucket_of(sample["read_utc"], publish_s)
        if pending and b != interval:
            row = local_sensors.derive_row(pending, cfg["calibration"], pending_s)
            local_sensors.write(_db, row)
            log.info("readings row written  ts=%s", row["ts"])
            co2_hist.append(row["co2_ppm"])
            if row["co2_ppm"] is None:
                scd41_shown = None
            pending = []
        interval, pending_s = b, publish_s
        pending.append(sample)

        now = local_sensors.derive_row([sample], cfg["calibration"], publish_s)
        if "scd41" in sample:
            scd41_shown = sample["scd41"]
        for key in ("pm1", "pm25", "pm10"):
            pm_hist[key].append(now[key])
        for key in ("oxidising", "reducing", "ammonia"):
            gas_hist[key].append(now[key])
        outdoor, outdoor_temps, winds = read_outdoor()

        state = {
            # Indoor temperature and RH come from the SCD41, mounted clear of
            # the Pi's heat; pressure from the BME280.
            "indoor": {
                "temp_f": None if scd41_shown is None
                else local_sensors.c2f(scd41_shown["temperature_c"]),
                "humidity": None if scd41_shown is None else scd41_shown["rh"],
                "pressure": now["pressure"],
            },
            "pm": {k: now[k] for k in ("pm1", "pm25", "pm10")},
            "pm_hist": pm_hist,
            "gas": {k: now[k] for k in ("oxidising", "reducing", "ammonia")},
            "gas_hist": gas_hist,
            "co2": None if scd41_shown is None else scd41_shown["co2_ppm"],
            "co2_hist": co2_hist,
            "outdoor": outdoor,
            "outdoor_temp_hist": outdoor_temps,
            "wind_hist": winds,
            "thresholds": cfg["thresholds"],
        }
        disp.display(screens.render(page, state))

        page, near = wait_for_next_frame(page, near)
except KeyboardInterrupt:
    log.info("Stopped by user")
