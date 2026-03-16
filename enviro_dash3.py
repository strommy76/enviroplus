#!/usr/bin/env python3
"""
Path:        ~/projects/enviroplus/enviro_dash3.py
Description: AQM-inspired Enviro+ display layout (160×80 ST7735).
             Left strip  — vertical AQ color bar (PM2.5-based, green→red) with
                           white level marker.
             Center      — CO₂ ppm as dominant large value (placeholder until
                           SCD-41 arrives), temperature, RH, pressure below.
             Right       — PM2.5 large with bar, PM1/PM10 side by side,
                           PM sparkline at bottom.
             MQTT status — 4px dot, top-right corner.
             To activate: change ExecStart in enviro_dash.service to this file.

Changelog:
  2026-03-16 01:15:00 EDT  Initial implementation, AQM-345 inspired layout.
                           CO₂ is placeholder (---) until SCD-41 connected.
"""

import json
import logging
import os
import sqlite3
import time
from collections import deque
from datetime import datetime
from importlib.resources import files
from logging.handlers import RotatingFileHandler

import bme280
import paho.mqtt.client as mqtt
import smbus2
import st7735
from dotenv import load_dotenv
from enviroplus import gas
from ltr559 import LTR559
from PIL import Image, ImageDraw, ImageFont
from pms5003 import PMS5003, ReadTimeoutError, SerialTimeoutError

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
try:
    _mqtt.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    _mqtt.loop_start()
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
disp = st7735.ST7735(port=0, cs=1, dc="GPIO9", backlight="GPIO12",
                     rotation=270, spi_speed_hz=40000000)
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
BAR_BG  = (20,  24,  40)
CYAN    = (0,  215, 195)
GREEN   = (40, 215,  75)
YELLOW  = (235, 195,  0)
ORANGE  = (255, 125,  0)
RED     = (255,  45,  45)
WHITE   = (240, 240, 240)
DIM     = (55,  60,  80)

# ── Sensors ────────────────────────────────────────────────────────────────────
_bus           = smbus2.SMBus(1)
_bme_addr      = 0x76
_bme_params    = bme280.load_calibration_params(_bus, _bme_addr)
ltr559_sensor  = LTR559()
pms5003_sensor = PMS5003()

# ── CPU temp compensation ──────────────────────────────────────────────────────
_cpu_hist  = deque([45.0] * cfg["calibration"]["cpu_hist_size"],
                   maxlen=cfg["calibration"]["cpu_hist_size"])
CPU_FACTOR = 0.0


def c2f(c): return c * 9 / 5 + 32
def f2c(f): return (f - 32) * 5 / 9


def _cpu_temp():
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        return int(f.read()) / 1000.0


def _bme_sample():
    return bme280.sample(_bus, _bme_addr, _bme_params)


def _calibrate(cal_actual_f):
    global CPU_FACTOR
    if not cal_actual_f:
        CPU_FACTOR = 0.0
        return
    cal_actual_c = f2c(cal_actual_f)
    cal_raw_c    = sum(_bme_sample().temperature for _ in range(10)) / 10
    cal_cpu_c    = sum(_cpu_temp()               for _ in range(10)) / 10
    denom        = cal_raw_c - cal_actual_c
    CPU_FACTOR   = (cal_cpu_c - cal_raw_c) / denom if denom else 0.0
    logging.info(
        f"CPU_FACTOR={CPU_FACTOR:.2f} "
        f"(raw={cal_raw_c * 9 / 5 + 32:.1f}°F  cpu={cal_cpu_c:.1f}°C  actual={cal_actual_f}°F)"
    )


_calibrate(cfg["calibration"]["cal_actual_f"])


def read_temp_c():
    n = cfg["calibration"]["bme_samples"]
    raw = sum(_bme_sample().temperature for _ in range(n)) / n
    cpu = _cpu_temp()
    _cpu_hist.append(cpu)
    avg_cpu = sum(_cpu_hist) / len(_cpu_hist)
    return raw - ((avg_cpu - raw) / CPU_FACTOR) if CPU_FACTOR else raw


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


def pm25_color(v):
    t = cfg["thresholds"]["pm25"]
    if v <= t["green_max"]:
        return GREEN
    if v <= t["yellow_max"]:
        return YELLOW
    return RED


def pm_color(v, key):
    t = cfg["thresholds"][key]
    if v <= t["green_max"]:
        return GREEN
    if v <= t["yellow_max"]:
        return YELLOW
    return RED


def mqtt_color():
    if _mqtt_status == "ok":
        return GREEN
    if _mqtt_status == "fail":
        return RED
    return YELLOW


def pressure_desc(pres):
    if pres < 970:
        return "storm"
    if pres < 990:
        return "rain"
    if pres < 1010:
        return "chng"
    if pres < 1030:
        return "fair"
    return "dry"


# ── Layout constants ────────────────────────────────────────────────────────────
#   x:  0   11|12          88|89        159
#       BAR  |   CENTER      |   PM RIGHT
AQ_BAR_MAX = 100   # μg/m³ PM2.5 scale for color bar
BAR_W      = 12    # left AQ bar width
X_SEP1     = BAR_W           # 12
X_SEP2     = 89
MID_X0     = X_SEP1 + 1     # 13
RIGHT_X0   = X_SEP2 + 1     # 90
RIGHT_W    = W - RIGHT_X0   # 70
MID_W      = X_SEP2 - MID_X0  # 76
SPARK_H    = 21   # PM sparkline height (bottom of right col, y=59..79)
SPARK_Y    = H - SPARK_H    # 59

# ── PM sparkline history (70 points = RIGHT_W) ────────────────────────────────
pm1_hist  = deque([0.0] * RIGHT_W, maxlen=RIGHT_W)
pm25_hist = deque([0.0] * RIGHT_W, maxlen=RIGHT_W)
pm10_hist = deque([0.0] * RIGHT_W, maxlen=RIGHT_W)


# ── AQ color bar ───────────────────────────────────────────────────────────────
def draw_aq_bar(draw, pm25):
    """Gauge bar: dim outline, bottom-filled to current PM2.5 level.
    Fill color reflects current AQ quality."""
    pm = min(max(pm25, 0), AQ_BAR_MAX)
    # Outline
    draw.rectangle((0, 0, BAR_W - 1, H - 1), outline=DIM)
    # Fill from bottom up to current level
    fill_top = H - 2 - int(pm / AQ_BAR_MAX * (H - 3))
    if fill_top < H - 2:
        if pm25 <= 12:
            col = GREEN
        elif pm25 <= 35:
            col = YELLOW
        elif pm25 <= 55:
            col = ORANGE
        else:
            col = RED
        draw.rectangle((1, fill_top, BAR_W - 2, H - 2), fill=col)


# ── PM sparkline (overlapping, each on its own vmax) ──────────────────────────
def draw_pm_spark(draw, pm_max):
    for hist, col in [(pm10_hist, RED), (pm25_hist, YELLOW), (pm1_hist, CYAN)]:
        vmax = max(pm_max, 1)
        vals = list(hist)
        prev = None
        for i, v in enumerate(vals):
            norm = min(v / vmax, 1.0)
            py   = SPARK_Y + SPARK_H - 1 - int(norm * (SPARK_H - 2))
            px   = RIGHT_X0 + i
            if prev is not None:
                draw.line([prev, (px, py)], fill=col)
            prev = (px, py)


# ── Frame renderer ─────────────────────────────────────────────────────────────
def draw_frame(tf, hum, pres, pm1, pm25, pm10):
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    d    = cfg["display"]

    # Column separators
    draw.line((X_SEP1, 0, X_SEP1, H - 1), fill=SEP)
    draw.line((X_SEP2, 0, X_SEP2, H - 1), fill=SEP)

    # ── Left: AQ color bar ─────────────────────────────────────────────────────
    draw_aq_bar(draw, pm25)

    # ── MQTT status dot (top-right corner, 4×4px) ──────────────────────────────
    draw.ellipse((W - 6, 1, W - 1, 6), fill=mqtt_color())

    # ── Center: CO₂ dominant ───────────────────────────────────────────────────
    co2_str = f"{co2_ppm:.0f}" if co2_ppm is not None else "---"
    draw.text((MID_X0 + 2, 2),  "CO\u2082",  font=FONT_S,  fill=DIM)
    draw.text((MID_X0 + 2, 12), co2_str,     font=FONT_XL, fill=co2_color(co2_ppm))
    draw.text((MID_X0 + 2, 37), "ppm",       font=FONT_S,  fill=DIM)

    # Center divider
    draw.line((MID_X0, 48, X_SEP2 - 1, 48), fill=SEP)

    # Temperature + RH
    draw.text((MID_X0 + 2, 51), f"DB {tf:.1f}\u00b0F", font=FONT_M, fill=temp_color(tf))
    draw.text((MID_X0 + 2, 65), f"RH {hum:.0f}%",   font=FONT_S, fill=hum_color(hum))

    # Pressure (description + hPa)
    pdesc = pressure_desc(pres)
    draw.text((MID_X0 + 38, 65), f"{pdesc} {pres:.0f}", font=FONT_S, fill=DIM)

    # ── Right: PM ─────────────────────────────────────────────────────────────
    # PM2.5 — dominant value
    p25c = pm25_color(pm25)
    draw.text((RIGHT_X0 + 2, 1),  "PM2.5",      font=FONT_S, fill=DIM)
    draw.text((RIGHT_X0 + 2, 11), f"{pm25:.1f}", font=FONT_L, fill=p25c)

    # PM2.5 bar (full right-col width, 3px)
    draw.rectangle((RIGHT_X0, 29, W - 1, 31), fill=BAR_BG)
    fill_w = int((RIGHT_W - 1) * min(pm25 / d["pm_bar_max"], 1.0))
    if fill_w > 0:
        draw.rectangle((RIGHT_X0, 29, RIGHT_X0 + fill_w, 31), fill=p25c)

    # PM1 / PM10 side by side
    mid_pm = RIGHT_X0 + RIGHT_W // 2
    draw.text((RIGHT_X0 + 2, 34), "PM1",         font=FONT_S, fill=DIM)
    draw.text((mid_pm + 2,   34), "PM10",         font=FONT_S, fill=DIM)
    draw.text((RIGHT_X0 + 2, 44), f"{pm1:.0f}",  font=FONT_M, fill=pm_color(pm1,  "pm1"))
    draw.text((mid_pm + 2,   44), f"{pm10:.0f}",  font=FONT_M, fill=pm_color(pm10, "pm10"))

    # Sparkline separator + plot
    draw.line((RIGHT_X0, SPARK_Y - 1, W - 1, SPARK_Y - 1), fill=SEP)
    draw_pm_spark(draw, d["pm_bar_max"])

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

        temp_c  = read_temp_c()
        _sample = _bme_sample()
        hum     = _sample.humidity
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
        except (ReadTimeoutError, SerialTimeoutError):
            try:
                pms5003_sensor = PMS5003()
            except Exception as e:
                logging.warning(f"PMS5003 reinit failed: {e}")

        tf = c2f(temp_c)
        pm1_hist.append(pm1)
        pm25_hist.append(pm25)
        pm10_hist.append(pm10)

        draw_frame(tf, hum, pres, pm1, pm25, pm10)

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
