#!/usr/bin/env python3
"""
Path:        ~/projects/enviroplus/enviro_dash3.py
Description: AQM-inspired Enviro+ display layout (160×80 ST7735).
             Left strip  — vertical EPA AQI bar (0-500, 6-band color scale)
                           computed from PM2.5 and PM10 sub-indices.
             Center      — CO₂ ppm as dominant large value (placeholder until
                           SCD-41 arrives), temperature, RH, pressure below.
             Right       — PM2.5 large with bar, PM1/PM10 side by side,
                           PM sparkline at bottom.
             MQTT status — 4px dot, top-right corner.
             To activate: change ExecStart in enviro_dash.service to this file.

Changelog:
  2026-03-16 01:15:00 EDT  Initial implementation, AQM-345 inspired layout.
                           CO₂ is placeholder (---) until SCD-41 connected.
  2026-03-16 02:30:00 EDT  Replace raw PM2.5 bar with proper EPA AQI (0-500).
                           AQI = max(PM2.5 sub-index, PM10 sub-index) per EPA
                           linear interpolation breakpoints. Added PURPLE and
                           MAROON for Very Unhealthy / Hazardous bands.
  2026-03-16 03:00:00 EDT  Remove DB/RH labels; enlarge temp+RH to FONT_L,
                           side-by-side. Remove pressure display. Replace right
                           column PM bar/values with PM+VOC dual line plots
                           (same overlapping draw_lines style as dash2).
  2026-03-16 04:00:00 EDT  Humidity correction for BME280 self-heating: apply
                           Magnus formula RH_actual = RH_sensor × Psat(T_chip)
                           / Psat(T_room). T_chip is raw BME280 reading; T_room
                           is CPU-compensated value. Also update cal_actual_f
                           to 75.1°F per overnight hygrometer reference.
  2026-03-16 03:30:00 EDT  Plot backgrounds tinted by worst-case severity:
                           PM panel uses EPA AQI band color; VOC panel uses
                           config thresholds (ox/rd/nh3). Dark 25% blend keeps
                           lines readable at all severity levels.
  2026-03-16 00:00:00 EDT  Pi 5 port: move all hardware-specific values to
                           config/env. Display SPI/GPIO, I2C bus, BME280 addr,
                           PMS5003 serial device, and CPU temp path are now
                           read from dynamic_config.json ["hardware"] and .env.
                           Switch bme280 to Pimoroni BME280 class API
                           (pimoroni-bme280 shadows RPi.bme280 in venv);
                           _bme_sample() return interface unchanged.
                           Add cpu_factor_override to _calibrate(): if set in
                           config, skips startup sampling and uses the value
                           directly. Pi 5 BME280 is at ~35°C cold-start vs
                           ~35°C steady-state but CPU is hotter at startup,
                           making computed factor wrong. Set null to revert.
  2026-03-18 09:30:00 EDT  Fix MQTT silent failure on DNS-delayed startup: move
                           loop_start() before connect() so network thread always
                           runs. Add is_connected() check + reconnect in
                           write_mqtt() so messages aren't silently queued when
                           connection was never established.
"""

import json
import logging
import math
import os
import sqlite3
import time
from collections import deque
from datetime import datetime
from importlib.resources import files
from logging.handlers import RotatingFileHandler
from types import SimpleNamespace

import bme280
import paho.mqtt.client as mqtt
import smbus2
import st7735
from dotenv import load_dotenv
from enviroplus import gas
from ltr559 import LTR559
from PIL import Image, ImageDraw, ImageFont
from pms5003 import PMS5003, ChecksumMismatchError, ReadTimeoutError, SerialTimeoutError

load_dotenv()

UserFont = str(files("font_roboto.files").joinpath("Roboto-Medium.ttf"))

# ── Paths ──────────────────────────────────────────────────────────────────────
_BASE       = os.environ.get("BASE_PATH",    "/home/pistrommy/projects/enviroplus")
LOG_PATH    = os.environ.get("LOG_PATH",    os.path.join(_BASE, "enviro.log"))
CONFIG_PATH = os.environ.get("CONFIG_PATH", os.path.join(_BASE, "dynamic_config.json"))
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(_BASE, "enviro.db"))

# ── Logging ────────────────────────────────────────────────────────────────────
_log_fmt      = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_handler_file = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=5)
_handler_file.setFormatter(_log_fmt)
_handler_con  = logging.StreamHandler()
_handler_con.setFormatter(_log_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_handler_file, _handler_con])

# ── Dynamic config ─────────────────────────────────────────────────────────────
_config_mtime = 0.0


def load_config():
    global _config_mtime
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    _config_mtime = os.path.getmtime(CONFIG_PATH)
    return cfg


cfg = load_config()

# ── MQTT (Adafruit IO) ────────────────────────────────────────────────────────
MQTT_BROKER = os.environ.get("MQTT_BROKER", "io.adafruit.com")
MQTT_PORT   = int(os.environ.get("MQTT_PORT", 1883))
MQTT_USER   = os.environ.get("MQTT_USER", "")
MQTT_KEY    = os.environ.get("MQTT_KEY",  "")

_mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
_mqtt.username_pw_set(MQTT_USER, MQTT_KEY)
_mqtt.loop_start()  # always start network thread; connect/reconnect handled separately
try:
    _mqtt.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
except Exception as e:
    logging.warning(f"MQTT connect failed at startup: {e} — will retry on publish")


def _round_readings(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
    """Single source of truth for sensor rounding — used by MQTT and SQLite."""
    return {
        "temperature": round(temp_f, 1), "humidity":  round(hum,    1),
        "pressure":    round(pres,   2), "light":     round(lux,    1),
        "oxidising":   round(ox,     1), "reducing":  round(rd,     1),
        "ammonia":     round(nh3,    1), "pm1":       round(pm1,    1),
        "pm25":        round(pm25,   1), "pm10":      round(pm10,   1),
    }


_mqtt_status = "init"  # "init" | "ok" | "fail"


def write_mqtt(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
    global _mqtt_status
    try:
        if not _mqtt.is_connected():
            _mqtt.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        r = _round_readings(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10)
        feeds = {
            "temperature": r["temperature"], "humidity": r["humidity"],
            "pressure":    r["pressure"],    "light":    r["light"],
            "oxidising":   r["oxidising"],   "reducing": r["reducing"],
            "ammonia":     r["ammonia"],     "pm01":     r["pm1"],
            "pm025":       r["pm25"],        "pm10":     r["pm10"],
        }
        for feed, val in feeds.items():
            _mqtt.publish(f"{MQTT_USER}/feeds/{feed}", val)
            time.sleep(0.5)
        _mqtt_status = "ok"
        logging.info("MQTT published to Adafruit IO")
    except Exception as e:
        _mqtt_status = "fail"
        logging.warning(f"MQTT publish failed: {e}")


# ── SQLite ─────────────────────────────────────────────────────────────────────
_db = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
_db.execute("PRAGMA journal_mode=WAL")
_db.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        ts          TEXT PRIMARY KEY,
        temp_f      REAL, humidity REAL, pressure REAL, lux REAL,
        oxidising   REAL, reducing REAL, ammonia  REAL,
        pm1         REAL, pm25     REAL, pm10     REAL,
        cpu_temp_c  REAL, cpu_load REAL, mem_free_mb REAL, uptime_s INTEGER
    )
""")
for col, typedef in [("cpu_temp_c", "REAL"), ("cpu_load", "REAL"),
                     ("mem_free_mb", "REAL"), ("uptime_s", "INTEGER")]:
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
    try:
        r = _round_readings(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10)
        cpu_temp, cpu_load, mem_free_mb, uptime_s = _pi_telemetry()
        _db.execute(
            "INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             r["temperature"], r["humidity"], r["pressure"], r["light"],
             r["oxidising"],   r["reducing"], r["ammonia"],
             r["pm1"],         r["pm25"],     r["pm10"],
             round(cpu_temp, 1), round(cpu_load, 2), round(mem_free_mb, 1), uptime_s)
        )
        _db.commit()
        logging.info("SQLite row written")
    except Exception as e:
        logging.warning(f"SQLite write failed: {e}")


# ── Display ────────────────────────────────────────────────────────────────────
_hw = cfg["hardware"]
disp = st7735.ST7735(port=_hw["spi_port"], cs=_hw["spi_cs"],
                     dc=_hw["display_dc"], backlight=_hw["display_backlight"],
                     rotation=_hw["display_rotation"],
                     spi_speed_hz=_hw["spi_speed_hz"])
disp.begin()
W, H = disp.width, disp.height  # 160 × 80

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_S  = ImageFont.truetype(UserFont, 9)   #  9px tall
FONT_M  = ImageFont.truetype(UserFont, 12)  # 12px tall
FONT_L  = ImageFont.truetype(UserFont, 18)  # 17px tall
FONT_XL = ImageFont.truetype(UserFont, 24)  # 23px tall — CO₂ dominant value

# ── Palette ────────────────────────────────────────────────────────────────────
BG      = (8,    8,  16)
SEP     = (25,  30,  50)
CYAN    = (0,  215, 195)
GREEN   = (40, 215,  75)
YELLOW  = (235, 195,  0)
ORANGE  = (255, 125,  0)
RED     = (255,  45,  45)
PURPLE  = (148,   0, 211)   # EPA "Very Unhealthy" (AQI 201-300)
MAROON  = (126,   0,  35)   # EPA "Hazardous"      (AQI 301-500)
MAGENTA = (205,  45, 205)   # NH3 VOC trace
WHITE   = (240, 240, 240)
DIM     = (55,  60,  80)

# ── Sensors ────────────────────────────────────────────────────────────────────
_i2c_bus       = int(os.environ.get("I2C_BUS", 1))
_pms_device    = os.environ.get("PMS5003_DEVICE", "/dev/ttyAMA0")
_cpu_temp_path = os.environ.get("CPU_TEMP_PATH", "/sys/class/thermal/thermal_zone0/temp")
_bus           = smbus2.SMBus(_i2c_bus)
_bme_addr      = _hw["bme280_addr"]
_bme_sensor    = bme280.BME280(i2c_addr=_bme_addr, i2c_dev=_bus)
ltr559_sensor  = LTR559()
pms5003_sensor = PMS5003(device=_pms_device)

# ── CPU temp compensation ──────────────────────────────────────────────────────
_cpu_hist  = deque([45.0] * cfg["calibration"]["cpu_hist_size"],
                   maxlen=cfg["calibration"]["cpu_hist_size"])
CPU_FACTOR = 0.0


def c2f(c): return c * 9 / 5 + 32
def f2c(f): return (f - 32) * 5 / 9


def _cpu_temp():
    with open(_cpu_temp_path) as f:
        return int(f.read()) / 1000.0


def _bme_sample():
    _bme_sensor.update_sensor()
    return SimpleNamespace(temperature=_bme_sensor.temperature,
                           humidity=_bme_sensor.humidity,
                           pressure=_bme_sensor.pressure)


def _calibrate(cal_actual_f):
    global CPU_FACTOR
    override = cfg["calibration"].get("cpu_factor_override")
    if override is not None:
        CPU_FACTOR = float(override)
        logging.info(f"CPU_FACTOR={CPU_FACTOR:.4f} (override from config)")
        return
    if not cal_actual_f:
        CPU_FACTOR = 0.0
        return
    cal_actual_c = f2c(cal_actual_f)
    cal_raw_c    = sum(_bme_sample().temperature for _ in range(10)) / 10
    cal_cpu_c    = sum(_cpu_temp()               for _ in range(10)) / 10
    denom        = cal_raw_c - cal_actual_c
    CPU_FACTOR   = (cal_cpu_c - cal_raw_c) / denom if denom else 0.0
    logging.info(
        f"CPU_FACTOR={CPU_FACTOR:.2f}  "
        f"raw={c2f(cal_raw_c):.1f}°F  cpu={cal_cpu_c:.1f}°C  actual={cal_actual_f}°F"
    )


_calibrate(cfg["calibration"]["cal_actual_f"])


def read_temp_c():
    """Returns (compensated_c, raw_chip_c). raw_chip_c is used for RH correction."""
    n = cfg["calibration"]["bme_samples"]
    raw = sum(_bme_sample().temperature for _ in range(n)) / n
    cpu = _cpu_temp()
    _cpu_hist.append(cpu)
    avg_cpu = sum(_cpu_hist) / len(_cpu_hist)
    comp = raw - ((avg_cpu - raw) / CPU_FACTOR) if CPU_FACTOR else raw
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


# ── CO₂ placeholder — assign real value here when SCD-41 is connected ─────────
# co2_ppm = scd41.measure_single_shot(); co2_ppm = data.co2
co2_ppm = None


# ── Color helpers ───────────────────────────────────────────────────────────────
def temp_color(f):
    t = cfg["thresholds"]["temp_f"]
    if t["green_min"] <= f <= t["green_max"]:
        return GREEN
    if t["yellow_min"] <= f <= t["yellow_max"]:
        return YELLOW
    return ORANGE


def hum_color(h):
    t = cfg["thresholds"]["humidity"]
    if t["green_min"] <= h <= t["green_max"]:
        return GREEN
    if t["yellow_min"] <= h <= t["yellow_max"]:
        return YELLOW
    return ORANGE


def co2_color(ppm):
    """Quality bands per ASHRAE / EPA guidance."""
    if ppm is None:
        return DIM
    if ppm < 800:
        return GREEN
    if ppm < 1200:
        return YELLOW
    if ppm < 2000:
        return ORANGE
    return RED


def mqtt_color():
    if _mqtt_status == "ok":
        return GREEN
    if _mqtt_status == "fail":
        return RED
    return YELLOW


def _aqi_color(aqi):
    """EPA AQI band color for the given AQI value."""
    if aqi <= 50:
        return GREEN
    if aqi <= 100:
        return YELLOW
    if aqi <= 150:
        return ORANGE
    if aqi <= 200:
        return RED
    if aqi <= 300:
        return PURPLE
    return MAROON


def _voc_severity(ox, rd, nh3):
    """Worst-case severity across all three gas channels using config thresholds.
    Oxidising: lower kΩ = more NO2 = worse.
    Reducing/NH3: lower kΩ = more gas = worse."""
    t = cfg["thresholds"]
    sev = 0  # 0=green, 1=yellow, 2=red
    if ox <= t["oxidising_k"]["green_max"]:
        sev = max(sev, 2)
    elif ox <= t["oxidising_k"]["yellow_max"]:
        sev = max(sev, 1)
    if rd < t["reducing_k"]["yellow_min"]:
        sev = max(sev, 2)
    elif rd < t["reducing_k"]["green_min"]:
        sev = max(sev, 1)
    if nh3 < t["ammonia_k"]["yellow_min"]:
        sev = max(sev, 2)
    elif nh3 < t["ammonia_k"]["green_min"]:
        sev = max(sev, 1)
    return [GREEN, YELLOW, RED][sev]


def _plot_bg(color, alpha=0.25):
    """Dark tint of severity color blended into BG at alpha — keeps lines readable."""
    return tuple(int(BG[i] + (color[i] - BG[i]) * alpha) for i in range(3))


# ── EPA AQI (PM2.5 + PM10 sub-indices) ─────────────────────────────────────────
# Breakpoints: (C_lo, C_hi, AQI_lo, AQI_hi)
_PM25_BP = [
    (  0.0,  12.0,   0,  50),
    ( 12.1,  35.4,  51, 100),
    ( 35.5,  55.4, 101, 150),
    ( 55.5, 150.4, 151, 200),
    (150.5, 250.4, 201, 300),
    (250.5, 350.4, 301, 400),
    (350.5, 500.4, 401, 500),
]
_PM10_BP = [
    (  0,  54,    0,  50),
    ( 55, 154,   51, 100),
    (155, 254,  101, 150),
    (255, 354,  151, 200),
    (355, 424,  201, 300),
    (425, 504,  301, 400),
    (505, 604,  401, 500),
]


def _aqi_sub(c, breakpoints):
    for c_lo, c_hi, aqi_lo, aqi_hi in breakpoints:
        if c <= c_hi:
            return round((aqi_hi - aqi_lo) / (c_hi - c_lo) * (c - c_lo) + aqi_lo)
    return 500


def pm_aqi(pm25, pm10):
    """EPA AQI: max of PM2.5 and PM10 sub-indices."""
    return max(_aqi_sub(pm25, _PM25_BP), _aqi_sub(pm10, _PM10_BP))


# ── Layout constants ────────────────────────────────────────────────────────────
#   x:  0   11|12          88|89        159
#       BAR  |   CENTER      |   PLOTS RIGHT
AQ_BAR_MAX = 500   # EPA AQI scale for color bar
BAR_W      = 12    # left AQ bar width
X_SEP1     = BAR_W           # 12
X_SEP2     = 89
MID_X0     = X_SEP1 + 1     # 13
RIGHT_X0   = X_SEP2 + 1     # 90
RIGHT_W    = W - RIGHT_X0   # 70
MID_W      = X_SEP2 - MID_X0  # 76
PLOT_H     = H // 2          # 40 — height of each plot half

# ── History buffers (70 points = RIGHT_W) ─────────────────────────────────────
pm1_hist  = deque([0.0] * RIGHT_W, maxlen=RIGHT_W)
pm25_hist = deque([0.0] * RIGHT_W, maxlen=RIGHT_W)
pm10_hist = deque([0.0] * RIGHT_W, maxlen=RIGHT_W)
ox_hist   = deque([0.0] * RIGHT_W, maxlen=RIGHT_W)
rd_hist   = deque([0.0] * RIGHT_W, maxlen=RIGHT_W)
nh3_hist  = deque([0.0] * RIGHT_W, maxlen=RIGHT_W)


# ── AQ color bar ───────────────────────────────────────────────────────────────
def draw_aq_bar(draw, aqi):
    """EPA AQI gauge: 6-band color scale 0-500, filled from bottom up to current
    AQI level, outline only above. Always shows at least a sliver of green."""
    val = max(aqi, 1)
    val = min(val, AQ_BAR_MAX)
    draw.rectangle((0, 0, BAR_W - 1, H - 1), outline=DIM)
    bands = [
        (  0,  50,  GREEN),
        ( 50, 100,  YELLOW),
        (100, 150,  ORANGE),
        (150, 200,  RED),
        (200, 300,  PURPLE),
        (300, 500,  MAROON),
    ]
    for lo, hi, col in bands:
        if lo >= val:
            break
        effective_hi = min(hi, val)
        y_top = H - 2 - int(effective_hi / AQ_BAR_MAX * (H - 3))
        y_bot = H - 2 - int(lo          / AQ_BAR_MAX * (H - 3))
        draw.rectangle((1, y_top, BAR_W - 2, y_bot), fill=col)


# ── Line plot (multiple overlapping series, each on its own vmax) ──────────────
def draw_lines(draw, histories, colors, vmaxes, x0, y0, w, h):
    for hist, col, vmax in zip(histories, colors, vmaxes):
        vmax = max(vmax, 1)
        vals = list(hist)
        prev = None
        for i, v in enumerate(vals):
            norm = min(v / vmax, 1.0)
            py   = y0 + h - 1 - int(norm * (h - 2))
            px   = x0 + i
            if prev is not None:
                draw.line([prev, (px, py)], fill=col)
            prev = (px, py)


# ── Frame renderer ─────────────────────────────────────────────────────────────
def draw_frame(tf, hum, pm1, pm25, pm10, ox, rd, nh3):
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    d    = cfg["display"]

    # Column separators
    draw.line((X_SEP1, 0, X_SEP1, H - 1), fill=SEP)
    draw.line((X_SEP2, 0, X_SEP2, H - 1), fill=SEP)

    # ── Left: AQ color bar (EPA AQI) ───────────────────────────────────────────
    aqi = pm_aqi(pm25, pm10)
    draw_aq_bar(draw, aqi)

    # ── MQTT status dot (top-right corner, 4×4px) ──────────────────────────────
    draw.ellipse((W - 6, 1, W - 1, 6), fill=mqtt_color())

    # ── Center: CO₂ dominant ───────────────────────────────────────────────────
    co2_str = f"{co2_ppm:.0f}" if co2_ppm is not None else "---"
    draw.text((MID_X0 + 2, 2),  "CO\u2082",  font=FONT_S,  fill=DIM)
    draw.text((MID_X0 + 2, 12), co2_str,     font=FONT_XL, fill=co2_color(co2_ppm))
    draw.text((MID_X0 + 2, 37), "ppm",       font=FONT_S,  fill=DIM)

    # Center divider
    draw.line((MID_X0, 48, X_SEP2 - 1, 48), fill=SEP)

    # Temperature + RH — no labels, side-by-side, FONT_L
    draw.text((MID_X0 + 2,  54), f"{tf:.0f}\u00b0F", font=FONT_L, fill=temp_color(tf))
    draw.text((MID_X0 + 44, 54), f"{hum:.0f}%",      font=FONT_L, fill=hum_color(hum))

    # ── Right: PM (top) + VOC (bottom) line plots ──────────────────────────────
    draw.rectangle((RIGHT_X0, 0,          W - 1, PLOT_H - 1), fill=_plot_bg(_aqi_color(aqi)))
    draw.rectangle((RIGHT_X0, PLOT_H + 1, W - 1, H - 1),      fill=_plot_bg(_voc_severity(ox, rd, nh3)))
    draw.line((RIGHT_X0, PLOT_H, W - 1, PLOT_H), fill=SEP)

    pm_max = d["pm_bar_max"]
    draw_lines(draw,
               [pm10_hist, pm25_hist, pm1_hist],
               [RED, YELLOW, CYAN],
               [pm_max, pm_max, pm_max],
               RIGHT_X0, 0, RIGHT_W, PLOT_H)

    draw_lines(draw,
               [nh3_hist, rd_hist, ox_hist],
               [MAGENTA, CYAN, YELLOW],
               [d["nh3_bar_max_k"], d["rd_bar_max_k"], d["ox_bar_max_k"]],
               RIGHT_X0, PLOT_H + 1, RIGHT_W, PLOT_H - 1)

    draw.text((RIGHT_X0 + 2, 1),          "PM",  font=FONT_S, fill=DIM)
    draw.text((RIGHT_X0 + 2, PLOT_H + 1), "VOC", font=FONT_S, fill=DIM)

    disp.display(img)


# ── Main loop ─────────────────────────────────────────────────────────────────
pm1 = pm25 = pm10 = 0.0
_last_publish = time.time()

logging.info("Enviro+ dash v3 starting")

while True:
    try:
        # Hot-reload config if file changed
        if os.path.getmtime(CONFIG_PATH) != _config_mtime:
            old_cal  = cfg["calibration"]["cal_actual_f"]
            old_hist = cfg["calibration"]["cpu_hist_size"]
            cfg = load_config()
            logging.info("dynamic_config.json reloaded")
            if cfg["calibration"]["cpu_hist_size"] != old_hist:
                new_size = cfg["calibration"]["cpu_hist_size"]
                _cpu_hist.__init__(list(_cpu_hist)[-new_size:], maxlen=new_size)
            if cfg["calibration"]["cal_actual_f"] != old_cal:
                _calibrate(cfg["calibration"]["cal_actual_f"])

        temp_c, raw_c = read_temp_c()
        _sample = _bme_sample()
        hum     = correct_humidity(_sample.humidity, raw_c, temp_c)
        pres    = _sample.pressure
        lux     = ltr559_sensor.get_lux()

        g   = gas.read_all()
        ox  = g.oxidising / 1000
        rd  = g.reducing  / 1000
        nh3 = g.nh3       / 1000

        try:
            p    = pms5003_sensor.read()
            pm1  = float(p.pm_ug_per_m3(1.0))
            pm25 = float(p.pm_ug_per_m3(2.5))
            pm10 = float(p.pm_ug_per_m3(10))
        except (ReadTimeoutError, SerialTimeoutError, ChecksumMismatchError):
            try:
                pms5003_sensor.setup()  # reinit serial without re-claiming GPIO
            except Exception as e:
                logging.warning(f"PMS5003 reinit failed: {e}")

        tf = c2f(temp_c)
        pm1_hist.append(pm1)
        pm25_hist.append(pm25)
        pm10_hist.append(pm10)
        ox_hist.append(ox)
        rd_hist.append(rd)
        nh3_hist.append(nh3)

        draw_frame(tf, hum, pm1, pm25, pm10, ox, rd, nh3)

        now = time.time()
        if now - _last_publish >= cfg["intervals"]["publish_s"]:
            write_mqtt(tf, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10)
            write_sqlite(tf, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10)
            _last_publish = now

        time.sleep(cfg["intervals"]["display_refresh_s"])

    except KeyboardInterrupt:
        logging.info("Stopped by user")
        break
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        time.sleep(5)
