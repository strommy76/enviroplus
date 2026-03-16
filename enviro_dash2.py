#!/usr/bin/env python3
"""
Path:        ~/projects/enviroplus/enviro_dash2.py
Description: Alternative Enviro+ display layout (160×80 ST7735).
             Left column  — lux (bulb) and MQTT status (signal) state icons.
             Middle column — temperature, RH, heat index, barometric pressure icon.
             Right column  — PM1/2.5/10 line plot (top), VOC line plot (bottom).
             Same MQTT, SQLite, and dynamic_config hot-reload as enviro_dash.py.
             To activate: change ExecStart in enviro_dash.service to this file.

Changelog:
  2026-03-16 00:30:00 EDT  Initial implementation.
  2026-03-16 00:45:00 EDT  Replace noise/speaker (no mic on HAT) with MQTT
                           status signal icon (green=ok, yellow=init, red=fail).
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

UserFont  = str(files("font_roboto.files").joinpath("Roboto-Medium.ttf"))
ICONS_DIR = "/home/pistrommy/Pimoroni/enviroplus/examples/icons"

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
                     rotation=270, spi_speed_hz=10000000)
disp.begin()
W, H = disp.width, disp.height  # 160 × 80

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_S = ImageFont.truetype(UserFont, 9)   #  9px tall
FONT_M = ImageFont.truetype(UserFont, 12)  # 12px tall
FONT_L = ImageFont.truetype(UserFont, 18)  # 17px tall

# ── Palette ────────────────────────────────────────────────────────────────────
BG      = (8,    8,  16)
SEP     = (25,  30,  50)
CYAN    = (0,  215, 195)
GREEN   = (40, 215,  75)
YELLOW  = (235, 195,  0)
ORANGE  = (255, 125,  0)
RED     = (255,  45,  45)
MAGENTA = (205,  45, 205)
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


# ── Heat index (Rothfusz regression, NOAA) ─────────────────────────────────────
def heat_index_f(tf, rh):
    """Returns NOAA heat index for tf >= 80°F; below that, HI equals tf."""
    if tf < 80:
        return tf
    return (-42.379
            + 2.04901523  * tf
            + 10.14333127 * rh
            - 0.22475541  * tf * rh
            - 6.83783e-3  * tf ** 2
            - 5.391553e-2 * rh ** 2
            + 1.22874e-3  * tf ** 2 * rh
            + 8.5282e-4   * tf * rh ** 2
            - 1.99e-6     * tf ** 2 * rh ** 2)


# ── Pressure description → icon filename key ────────────────────────────────────
def pressure_desc(pres):
    if pres < 970:
        return "storm"
    if pres < 990:
        return "rain"
    if pres < 1010:
        return "change"
    if pres < 1030:
        return "fair"
    return "dry"


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
    return RED


def hi_color(hi):
    """NOAA heat index risk bands."""
    if hi < 80:
        return GREEN
    if hi < 90:
        return YELLOW
    if hi < 103:
        return ORANGE
    return RED


def lux_color(lux):
    if lux < 50:
        return DIM
    if lux < 100:
        return YELLOW
    if lux < 500:
        return GREEN
    return WHITE


def mqtt_color():
    if _mqtt_status == "ok":
        return GREEN
    if _mqtt_status == "fail":
        return RED
    return YELLOW  # "init" — not yet published


# ── Pixel icons (PIL primitives) ───────────────────────────────────────────────
def icon_bulb(draw, x, y, col):
    """Lightbulb ~18×20px. x,y = top-left."""
    draw.ellipse((x, y, x + 17, y + 13), fill=col)
    draw.rectangle((x + 4, y + 13, x + 13, y + 19), fill=col)
    draw.line([(x + 4, y + 15), (x + 13, y + 15)], fill=BG)
    draw.line([(x + 4, y + 18), (x + 13, y + 18)], fill=BG)


def icon_signal(draw, x, y, col):
    """WiFi-style signal icon ~18×14px. x,y = top-left."""
    draw.ellipse((x + 7, y + 11, x + 10, y + 13), fill=col)
    draw.arc((x + 4, y + 7, x + 13, y + 12), 210, 330, fill=col)
    draw.arc((x + 1, y + 3, x + 16, y + 11), 210, 330, fill=col)
    draw.arc((x + 0, y + 0, x + 17, y + 10), 210, 330, fill=col)


# ── Layout constants ────────────────────────────────────────────────────────────
#   x:  0    24|25    93|94        159
#       LEFT   |  MID   |   RIGHT
#   y:  0..79 throughout; right column split at y=40
X_SEP1   = 24           # separator: left | mid
X_SEP2   = 94           # separator: mid  | right
MID_X0   = X_SEP1 + 1  # 25
RIGHT_X0 = X_SEP2 + 1  # 95
PLOT_W   = W - RIGHT_X0 # 65 — pixels wide per plot (one pixel per data point)
PLOT_H   = H // 2       # 40 — height of each plot half

# ── History buffers (65 points — one per plot pixel column) ───────────────────
pm1_hist  = deque([0.0] * PLOT_W, maxlen=PLOT_W)
pm25_hist = deque([0.0] * PLOT_W, maxlen=PLOT_W)
pm10_hist = deque([0.0] * PLOT_W, maxlen=PLOT_W)
ox_hist   = deque([0.0] * PLOT_W, maxlen=PLOT_W)
rd_hist   = deque([0.0] * PLOT_W, maxlen=PLOT_W)
nh3_hist  = deque([0.0] * PLOT_W, maxlen=PLOT_W)

# ── Pressure icon cache (open + resize once, reuse every frame) ────────────────
_picon_cache: dict = {}


def _pres_icon(desc):
    if desc not in _picon_cache:
        icon = Image.open(os.path.join(ICONS_DIR, f"weather-{desc}.png")).convert("RGBA")
        icon.thumbnail((18, 18))
        _picon_cache[desc] = icon
    return _picon_cache[desc]


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
def draw_frame(tf, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    d    = cfg["display"]

    # Vertical column separators + horizontal plot divider
    draw.line((X_SEP1, 0, X_SEP1, H - 1),        fill=SEP)
    draw.line((X_SEP2, 0, X_SEP2, H - 1),        fill=SEP)
    draw.line((RIGHT_X0, PLOT_H, W - 1, PLOT_H), fill=SEP)

    # ── Left column: lux state (bulb, top) and MQTT status (signal, bottom) ──
    icon_bulb(draw,   3, 10, lux_color(lux))    # centered in top half (y=10..29)
    icon_signal(draw, 3, 53, mqtt_color())       # centered in bottom half (y=53..66)

    # ── Middle column ──────────────────────────────────────────────────────────
    # Temperature                             y=3..15
    draw.text((MID_X0 + 1, 3),  f"{tf:.1f}\u00b0F", font=FONT_M, fill=temp_color(tf))
    # Relative humidity                       y=18..27
    draw.text((MID_X0 + 1, 18), f"RH {hum:.0f}%",   font=FONT_S, fill=hum_color(hum))
    # Heat index (label + large value)        y=29..56
    hi = heat_index_f(tf, hum)
    draw.text((MID_X0 + 1, 29), "HI",              font=FONT_S, fill=DIM)
    draw.text((MID_X0 + 1, 39), f"{hi:.0f}\u00b0F", font=FONT_L, fill=hi_color(hi))
    # Barometric pressure icon + hPa value    y=59..77
    pdesc = pressure_desc(pres)
    img.paste(_pres_icon(pdesc), (MID_X0 + 1, 59), mask=_pres_icon(pdesc))
    draw.text((MID_X0 + 21, 63), f"{pres:.0f}", font=FONT_S, fill=DIM)

    # ── Right column: line plots ───────────────────────────────────────────────
    # PM top half — PM10 (red) drawn first so PM1 (cyan) is most visible on top
    pm_max = d["pm_bar_max"]
    draw_lines(draw,
               [pm10_hist, pm25_hist, pm1_hist],
               [RED, YELLOW, CYAN],
               [pm_max, pm_max, pm_max],
               RIGHT_X0, 0, PLOT_W, PLOT_H)

    # VOC bottom half — each series on its own kΩ scale
    draw_lines(draw,
               [nh3_hist, rd_hist, ox_hist],
               [MAGENTA, CYAN, YELLOW],
               [d["nh3_bar_max_k"], d["rd_bar_max_k"], d["ox_bar_max_k"]],
               RIGHT_X0, PLOT_H + 1, PLOT_W, PLOT_H - 1)

    # Section labels drawn last (over the plots)
    draw.text((RIGHT_X0 + 2, 1),          "PM",  font=FONT_S, fill=DIM)
    draw.text((RIGHT_X0 + 2, PLOT_H + 1), "VOC", font=FONT_S, fill=DIM)

    disp.display(img)


# ── Main loop ─────────────────────────────────────────────────────────────────
pm1 = pm25 = pm10 = 0.0
_last_publish = time.time()

logging.info("Enviro+ dash v2 starting")

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
        ox_hist.append(ox)
        rd_hist.append(rd)
        nh3_hist.append(nh3)

        draw_frame(tf, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10)

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
