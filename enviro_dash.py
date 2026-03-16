#!/usr/bin/env python3
"""
Path:        ~/projects/enviroplus/enviro_dash.py
Description: High-density dashboard for Enviro+ (160×80 ST7735 display).
             Displays all 10 sensors with color-coded bar graphs and dual
             sparklines (temp + PM2.5). Publishes to Adafruit IO via MQTT
             and logs to SQLite. All tuning values hot-reloaded from
             dynamic_config.json with no restart required.

Usage:       python3 enviro_dash.py
             (normally managed by systemd: enviro_dash.service)

Changelog:
  2026-03-15 23:34:22 EDT  Initial working dashboard with MQTT, SQLite,
                           systemd service, rotating log, CPU temp
                           compensation, dynamic_config.json hot-reload,
                           BME280 averaging, Pi telemetry logging, and
                           Adafruit IO rate-limit throttling.
  2026-03-15 23:53:35 EDT  Simplify pass: BASE_PATH eliminates repeated path
                           literals; f2c() helper used in _calibrate();
                           _round_readings() is now single source of truth
                           for sensor rounding shared by MQTT and SQLite.
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

# from influxdb_client import InfluxDBClient, Point
# from influxdb_client.client.write_api import SYNCHRONOUS

UserFont = str(files("font_roboto.files").joinpath("Roboto-Medium.ttf"))

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE = os.environ.get("BASE_PATH", "/home/pistrommy/projects/enviroplus")
LOG_PATH    = os.environ.get("LOG_PATH",    os.path.join(_BASE, "enviro.log"))
CONFIG_PATH = os.environ.get("CONFIG_PATH", os.path.join(_BASE, "dynamic_config.json"))
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(_BASE, "enviro.db"))

# ── Logging ───────────────────────────────────────────────────────────────────
_log_fmt = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_handler_file = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=5)
_handler_file.setFormatter(_log_fmt)
_handler_console = logging.StreamHandler()
_handler_console.setFormatter(_log_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_handler_file, _handler_console])

# ── Dynamic config ────────────────────────────────────────────────────────────
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
MQTT_KEY    = os.environ.get("MQTT_KEY", "")

_mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
_mqtt.username_pw_set(MQTT_USER, MQTT_KEY)
try:
    _mqtt.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    _mqtt.loop_start()
except Exception as e:
    logging.warning(f"MQTT connect failed at startup: {e} — will retry on publish")


def write_mqtt(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
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
        logging.info("MQTT published to Adafruit IO")
    except Exception as e:
        logging.warning(f"MQTT publish failed: {e}")


# ── SQLite ────────────────────────────────────────────────────────────────────

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
        pass  # column already exists
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


# ── InfluxDB (pending setup) ──────────────────────────────────────────────────
# INFLUX_URL    = os.environ.get("INFLUX_URL",    "http://100.x.x.x:8086")
# INFLUX_TOKEN  = os.environ.get("INFLUX_TOKEN",  "")
# INFLUX_ORG    = os.environ.get("INFLUX_ORG",    "home")
# INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "enviroplus")
# _influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
# _write  = _influx.write_api(write_options=SYNCHRONOUS)
# def write_influx(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
#     ...swap write_mqtt for write_influx in main loop when ready

# ── Display ───────────────────────────────────────────────────────────────────
disp = st7735.ST7735(port=0, cs=1, dc="GPIO9", backlight="GPIO12",
                     rotation=270, spi_speed_hz=10000000)
disp.begin()
W, H = disp.width, disp.height  # 160 × 80

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_S = ImageFont.truetype(UserFont, 9)
FONT_M = ImageFont.truetype(UserFont, 12)

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = (8,   8,  16)
HEADER  = (0,  28,  55)
SEP     = (25, 30,  50)
BAR_BG  = (20, 24,  40)
CYAN    = (0, 215, 195)
GREEN   = (40, 215,  75)
YELLOW  = (235, 195,  0)
ORANGE  = (255, 125,  0)
RED     = (255,  45,  45)
MAGENTA = (205,  45, 205)
DIM     = (55,  60,  80)

# ── Sensors ───────────────────────────────────────────────────────────────────
_bus          = smbus2.SMBus(1)
_bme_addr     = 0x76
_bme_params   = bme280.load_calibration_params(_bus, _bme_addr)
ltr559_sensor = LTR559()
pms5003_sensor = PMS5003()

# ── CPU temp compensation ─────────────────────────────────────────────────────
_cpu_hist  = deque([45.0] * cfg["calibration"]["cpu_hist_size"],
                   maxlen=cfg["calibration"]["cpu_hist_size"])
CPU_FACTOR = 0.0


def _cpu_temp():
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        return int(f.read()) / 1000.0


def _bme_sample():
    return bme280.sample(_bus, _bme_addr, _bme_params)


def _calibrate(cal_actual_f):
    """Derive CPU_FACTOR from a known reference temperature."""
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


def c2f(c):
    return c * 9 / 5 + 32


def f2c(f):
    return (f - 32) * 5 / 9


def _round_readings(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
    """Single source of truth for sensor rounding — used by MQTT and SQLite."""
    return {
        "temperature": round(temp_f, 1),
        "humidity":    round(hum,    1),
        "pressure":    round(pres,   2),
        "light":       round(lux,    1),
        "oxidising":   round(ox,     1),
        "reducing":    round(rd,     1),
        "ammonia":     round(nh3,    1),
        "pm1":         round(pm1,    1),
        "pm25":        round(pm25,   1),
        "pm10":        round(pm10,   1),
    }


# ── Quality colors ────────────────────────────────────────────────────────────
def qcolor(val, good_max, warn_max):
    """Higher = worse (oxidising, PM)."""
    if val <= good_max:
        return GREEN
    if val <= warn_max:
        return YELLOW
    return RED


def iqcolor(val, warn_min, good_min):
    """Lower = worse (reducing, NH3)."""
    if val >= good_min:
        return GREEN
    if val >= warn_min:
        return YELLOW
    return RED


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


def aq_info(pm25):
    t = cfg["thresholds"]["aq_pm25"]
    if pm25 <= t["good"]:
        return "GOOD", GREEN
    if pm25 <= t["moderate"]:
        return "MOD", YELLOW
    if pm25 <= t["usg"]:
        return "USG", ORANGE
    if pm25 <= t["unhealthy"]:
        return "UNHL", RED
    return "HAZ", MAGENTA


# ── Pixel icons (PIL primitive drawing) ───────────────────────────────────────
def icon_therm(draw, x, y, col):
    """Thermometer, 7×10px."""
    draw.rectangle((x + 2, y, x + 4, y + 5), outline=col)
    draw.ellipse((x, y + 5, x + 6, y + 9), fill=col)
    draw.line([(x + 3, y + 2), (x + 3, y + 5)], fill=col)


def icon_drop(draw, x, y, col):
    """Water drop, 7×9px."""
    draw.polygon([(x + 3, y), (x + 6, y + 5), (x + 3, y + 8), (x, y + 5)], fill=col)


def icon_gas(draw, x, y, col):
    """Gas cloud (3 overlapping circles), 10×8px."""
    draw.ellipse((x + 0, y + 2, x + 4, y + 7), outline=col)
    draw.ellipse((x + 3, y + 0, x + 7, y + 5), outline=col)
    draw.ellipse((x + 5, y + 2, x + 9, y + 7), outline=col)


def icon_dust(draw, x, y, col):
    """Particulates (scattered dots), 10×7px."""
    for dx, dy in [(0, 2), (2, 0), (4, 3), (6, 1), (8, 2), (1, 5), (3, 4), (5, 6), (7, 5), (9, 3)]:
        draw.point((x + dx, y + dy), fill=col)


def icon_sun(draw, x, y, col):
    """Sun (circle + 8 rays), 9×9px."""
    draw.ellipse((x + 2, y + 2, x + 6, y + 6), outline=col)
    for dx, dy in [(4, 0), (4, 8), (0, 4), (8, 4)]:
        draw.point((x + dx, y + dy), fill=col)
    for dx, dy in [(1, 1), (7, 1), (1, 7), (7, 7)]:
        draw.point((x + dx, y + dy), fill=col)


# ── Bar graph ─────────────────────────────────────────────────────────────────
def draw_hbar(draw, x, y, w, h, frac, col):
    frac = max(0.0, min(1.0, frac))
    draw.rectangle((x, y, x + w - 1, y + h - 1), fill=BAR_BG)
    if frac > 0:
        draw.rectangle((x, y, x + max(1, int(w * frac)) - 1, y + h - 1), fill=col)


# ── History for dual sparkline ────────────────────────────────────────────────
SPARK_W   = (W - 1) // 2
temp_hist = deque([20.0] * SPARK_W, maxlen=SPARK_W)
pm25_hist = deque([0.0]  * SPARK_W, maxlen=SPARK_W)

# ── Layout Y constants ────────────────────────────────────────────────────────
Y_WX    = 11
Y_GAS   = 27
Y_PM    = 40
Y_AQ    = 53
Y_SPARK = 65
SPARK_H = H - Y_SPARK


def draw_frame(tf, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    d    = cfg["display"]
    thr  = cfg["thresholds"]

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle((0, 0, W - 1, 9), fill=HEADER)
    draw.text((3, 1), "ENVIRO+", font=FONT_S, fill=CYAN)
    now = datetime.now().strftime("%-I:%M %p")
    draw.text((W - 44, 1), now, font=FONT_S, fill=CYAN)
    draw.line((0, 10, W, 10), fill=SEP)

    # ── Weather row ───────────────────────────────────────────────────────────
    tc = temp_color(tf)
    icon_therm(draw, 2, Y_WX + 1, tc)
    draw.text((11, Y_WX), f"{tf:.1f}\u00b0F", font=FONT_M, fill=tc)
    draw_hbar(draw, 2, Y_WX + 13, 76, 3,
              (tf - d["temp_bar_min_f"]) / d["temp_bar_range_f"], tc)

    hc = hum_color(hum)
    icon_drop(draw, 84, Y_WX + 2, hc)
    draw.text((93, Y_WX + 2), f"H:{hum:.0f}%", font=FONT_S, fill=hc)
    draw_hbar(draw, 84, Y_WX + 13, 74, 3, hum / 100.0, hc)
    draw.line((0, 26, W, 26), fill=SEP)

    # ── Gas row ───────────────────────────────────────────────────────────────
    # Oxidising (NO2/O3): higher resistance = more pollution, baseline ~20k
    # Reducing (CO/VOCs): lower resistance = more pollution, baseline ~200k
    # NH3:                lower resistance = more pollution, baseline ~750k
    icon_gas(draw, 2, Y_GAS + 1, DIM)
    c_ox  = qcolor( ox,  thr["oxidising_k"]["green_max"],  thr["oxidising_k"]["yellow_max"])
    c_rd  = iqcolor(rd,  thr["reducing_k"]["yellow_min"],  thr["reducing_k"]["green_min"])
    c_nh3 = iqcolor(nh3, thr["ammonia_k"]["yellow_min"],   thr["ammonia_k"]["green_min"])
    draw.text((13,  Y_GAS), f"Ox:{ox:.0f}k",  font=FONT_S, fill=c_ox)
    draw.text((62,  Y_GAS), f"Rd:{rd:.0f}k",  font=FONT_S, fill=c_rd)
    draw.text((111, Y_GAS), f"N3:{nh3:.0f}k", font=FONT_S, fill=c_nh3)
    draw_hbar(draw, 13,  Y_GAS + 10, 44, 2, min(ox  / d["ox_bar_max_k"],  1.0), c_ox)
    draw_hbar(draw, 62,  Y_GAS + 10, 44, 2, max(0, 1 - rd  / d["rd_bar_max_k"]),  c_rd)
    draw_hbar(draw, 111, Y_GAS + 10, 44, 2, max(0, 1 - nh3 / d["nh3_bar_max_k"]), c_nh3)
    draw.line((0, 39, W, 39), fill=SEP)

    # ── PM row ────────────────────────────────────────────────────────────────
    icon_dust(draw, 2, Y_PM + 2, DIM)
    c_p1  = qcolor(pm1,  thr["pm1"]["green_max"],  thr["pm1"]["yellow_max"])
    c_p25 = qcolor(pm25, thr["pm25"]["green_max"], thr["pm25"]["yellow_max"])
    c_p10 = qcolor(pm10, thr["pm10"]["green_max"], thr["pm10"]["yellow_max"])
    draw.text((13,  Y_PM), f"1:{pm1:.0f}",    font=FONT_S, fill=c_p1)
    draw.text((62,  Y_PM), f"2.5:{pm25:.0f}", font=FONT_S, fill=c_p25)
    draw.text((111, Y_PM), f"10:{pm10:.0f}",  font=FONT_S, fill=c_p10)
    draw_hbar(draw, 13,  Y_PM + 10, 44, 2, min(pm1  / d["pm_bar_max"], 1.0), c_p1)
    draw_hbar(draw, 62,  Y_PM + 10, 44, 2, min(pm25 / d["pm_bar_max"], 1.0), c_p25)
    draw_hbar(draw, 111, Y_PM + 10, 44, 2, min(pm10 / d["pm_bar_max"], 1.0), c_p10)
    draw.line((0, 52, W, 52), fill=SEP)

    # ── Light + AQ row ────────────────────────────────────────────────────────
    icon_sun(draw, 2, Y_AQ + 1, CYAN)
    draw.text((13, Y_AQ + 1), f"Lux:{int(lux)}", font=FONT_S, fill=CYAN)
    draw.text((75, Y_AQ + 1), f"P:{pres:.0f}",   font=FONT_S, fill=DIM)
    label, badge_col = aq_info(pm25)
    draw.rectangle((119, Y_AQ, W - 2, Y_AQ + 10), fill=badge_col)
    draw.text((121, Y_AQ + 1), label, font=FONT_S, fill=BG)
    draw.line((0, 64, W, 64), fill=SEP)

    # ── Dual sparkline: temperature (left) | PM2.5 (right) ───────────────────
    mid = SPARK_W
    draw.text((1,     Y_SPARK), "T\u00b0F", font=FONT_S, fill=DIM)
    draw.text((mid + 2, Y_SPARK), "PM2.5",   font=FONT_S, fill=DIM)

    def draw_spark(hist, x0, col_fn):
        vals = list(hist)
        vmin, vmax = min(vals), max(vals)
        rng = max(vmax - vmin, 0.5)
        for i, v in enumerate(vals):
            norm = (v - vmin) / rng
            py = Y_SPARK + SPARK_H - 1 - int(norm * (SPARK_H - 2))
            draw.point((x0 + i, py), fill=col_fn(v))

    draw_spark(temp_hist, 0,       lambda v: temp_color(c2f(v)))
    draw.line((mid, Y_SPARK, mid, H - 1), fill=SEP)
    draw_spark(pm25_hist, mid + 1, lambda v: qcolor(v, thr["pm25"]["green_max"], thr["pm25"]["yellow_max"]))

    disp.display(img)


# ── Main loop ─────────────────────────────────────────────────────────────────
pm1 = pm25 = pm10 = 0.0
_last_publish = time.time()

logging.info("Enviro+ dashboard starting")

while True:
    try:
        # ── Hot-reload config if file changed ─────────────────────────────────
        if os.path.getmtime(CONFIG_PATH) != _config_mtime:
            old_cal = cfg["calibration"]["cal_actual_f"]
            old_hist_size = cfg["calibration"]["cpu_hist_size"]
            cfg = load_config()
            logging.info("dynamic_config.json reloaded")
            if cfg["calibration"]["cpu_hist_size"] != old_hist_size:
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

        temp_hist.append(temp_c)
        pm25_hist.append(pm25)
        tf = c2f(temp_c)
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
