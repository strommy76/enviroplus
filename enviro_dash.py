#!/usr/bin/env python3
"""
enviro_dash.py - High-density dashboard for Enviro+ (160×80 display)

All 10 sensors on one screen with pixel icons, color-coded bar graphs,
and dual sparklines (temp + PM2.5). Green=good, yellow=warning, red=danger.

Usage: python3 enviro_dash.py
"""

import os
import time
from dotenv import load_dotenv
load_dotenv()
import logging
from datetime import datetime
from collections import deque

import smbus2
import bme280
import st7735
from PIL import Image, ImageDraw, ImageFont
from importlib.resources import files
UserFont = str(files("font_roboto.files").joinpath("Roboto-Medium.ttf"))
from ltr559 import LTR559
from enviroplus import gas
from pms5003 import PMS5003, ReadTimeoutError, SerialTimeoutError
import json
import paho.mqtt.client as mqtt
# from influxdb_client import InfluxDBClient, Point
# from influxdb_client.client.write_api import SYNCHRONOUS

logging.basicConfig(
    format="%(asctime)s %(levelname)-5s %(message)s",
    level=logging.INFO, datefmt="%H:%M:%S")

# ── MQTT ──────────────────────────────────────────────────────────────────────
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.environ.get("MQTT_PORT", 1883))
MQTT_TOPIC  = os.environ.get("MQTT_TOPIC",  "enviroplus")

_mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
_mqtt.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
_mqtt.loop_start()

def write_mqtt(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
    try:
        payload = json.dumps({
            "temperature": round(temp_f, 1),
            "humidity":    round(hum,    1),
            "pressure":    round(pres,   2),
            "light":       round(lux,    1),
            "oxidising":   round(ox,     1),
            "reducing":    round(rd,     1),
            "nh3":         round(nh3,    1),
            "pm1":         round(pm1,    1),
            "pm2_5":       round(pm25,   1),
            "pm10":        round(pm10,   1),
        })
        _mqtt.publish(MQTT_TOPIC, payload)
    except Exception as e:
        logging.warning(f"MQTT publish failed: {e}")

# ── InfluxDB (pending setup) ───────────────────────────────────────────────────
# INFLUX_URL    = os.environ.get("INFLUX_URL",    "http://100.x.x.x:8086")
# INFLUX_TOKEN  = os.environ.get("INFLUX_TOKEN",  "")
# INFLUX_ORG    = os.environ.get("INFLUX_ORG",    "home")
# INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "enviroplus")
# _influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
# _write  = _influx.write_api(write_options=SYNCHRONOUS)
# def write_influx(temp_f, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10):
#     ...swap write_aio for write_influx in main loop when ready

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
_bus           = smbus2.SMBus(1)
_bme_addr      = 0x76
_bme_params    = bme280.load_calibration_params(_bus, _bme_addr)
ltr559_sensor  = LTR559()
pms5003_sensor = PMS5003()

# ── CPU temp compensation ─────────────────────────────────────────────────────
# Set to 0.0 when Enviro+ is physically separated from the Pi.
# Increase if still reading high when HAT is mounted directly on GPIO header.
CPU_FACTOR = 0.0

_cpu_hist = deque([45.0] * 5, maxlen=5)

def _cpu_temp():
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        return int(f.read()) / 1000.0

def _bme_sample():
    return bme280.sample(_bus, _bme_addr, _bme_params)

def read_temp_c():
    raw = _bme_sample().temperature
    cpu = _cpu_temp()
    _cpu_hist.append(cpu)
    avg_cpu = sum(_cpu_hist) / len(_cpu_hist)
    compensated = raw - ((avg_cpu - raw) / CPU_FACTOR) if CPU_FACTOR else raw
    return compensated

def c2f(c):
    return c * 9 / 5 + 32

# ── Quality colors ────────────────────────────────────────────────────────────
def qcolor(val, good_max, warn_max):
    if val <= good_max: return GREEN
    if val <= warn_max: return YELLOW
    return RED

def temp_color(f):
    if 65 <= f <= 80: return GREEN
    if 55 <= f <= 90: return YELLOW
    return ORANGE

def hum_color(h):
    if 30 <= h <= 70: return GREEN
    if 20 <= h <= 80: return YELLOW
    return RED

def aq_info(pm25):
    if pm25 <= 12:  return "GOOD", GREEN
    if pm25 <= 35:  return "MOD",  YELLOW
    if pm25 <= 55:  return "USG",  ORANGE
    if pm25 <= 150: return "UNHL", RED
    return "HAZ",   MAGENTA

# ── Pixel icons (PIL primitive drawing) ───────────────────────────────────────
def icon_therm(draw, x, y, col):
    """Thermometer, 7×10px."""
    draw.rectangle((x+2, y, x+4, y+5), outline=col)
    draw.ellipse((x, y+5, x+6, y+9), fill=col)
    draw.line([(x+3, y+2), (x+3, y+5)], fill=col)

def icon_drop(draw, x, y, col):
    """Water drop, 7×9px."""
    draw.polygon([(x+3, y), (x+6, y+5), (x+3, y+8), (x, y+5)], fill=col)

def icon_gas(draw, x, y, col):
    """Gas cloud (3 overlapping circles), 10×8px."""
    draw.ellipse((x+0, y+2, x+4, y+7), outline=col)
    draw.ellipse((x+3, y+0, x+7, y+5), outline=col)
    draw.ellipse((x+5, y+2, x+9, y+7), outline=col)

def icon_dust(draw, x, y, col):
    """Particulates (scattered dots), 10×7px."""
    for dx, dy in [(0,2),(2,0),(4,3),(6,1),(8,2),(1,5),(3,4),(5,6),(7,5),(9,3)]:
        draw.point((x+dx, y+dy), fill=col)

def icon_sun(draw, x, y, col):
    """Sun (circle + 8 rays), 9×9px."""
    draw.ellipse((x+2, y+2, x+6, y+6), outline=col)
    for dx, dy in [(4,0),(4,8),(0,4),(8,4)]:
        draw.point((x+dx, y+dy), fill=col)
    for dx, dy in [(1,1),(7,1),(1,7),(7,7)]:
        draw.point((x+dx, y+dy), fill=col)

# ── Bar graph ─────────────────────────────────────────────────────────────────
def draw_hbar(draw, x, y, w, h, frac, col):
    frac = max(0.0, min(1.0, frac))
    draw.rectangle((x, y, x+w-1, y+h-1), fill=BAR_BG)
    if frac > 0:
        draw.rectangle((x, y, x+int(w*frac)-1, y+h-1), fill=col)

# ── History for dual sparkline ────────────────────────────────────────────────
SPARK_W = (W - 1) // 2
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

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle((0, 0, W-1, 9), fill=HEADER)
    draw.text((3, 1), "ENVIRO+", font=FONT_S, fill=CYAN)
    now = datetime.now().strftime("%-I:%M %p")
    draw.text((W - 44, 1), now, font=FONT_S, fill=CYAN)
    draw.line((0, 10, W, 10), fill=SEP)

    # ── Weather row ───────────────────────────────────────────────────────────
    tc = temp_color(tf)
    icon_therm(draw, 2, Y_WX + 1, tc)
    draw.text((11, Y_WX), f"{tf:.1f}\u00b0F", font=FONT_M, fill=tc)
    draw_hbar(draw, 2, Y_WX + 13, 76, 3, (tf - 40) / 80.0, tc)

    hc = hum_color(hum)
    icon_drop(draw, 84, Y_WX + 2, hc)
    draw.text((93, Y_WX + 2), f"H:{hum:.0f}%", font=FONT_S, fill=hc)
    draw_hbar(draw, 84, Y_WX + 13, 74, 3, hum / 100.0, hc)
    draw.line((0, 26, W, 26), fill=SEP)

    # ── Gas row ───────────────────────────────────────────────────────────────
    icon_gas(draw, 2, Y_GAS + 1, DIM)
    c_ox  = qcolor(ox,   40,  50)
    c_rd  = qcolor(rd,  450, 550)
    c_nh3 = qcolor(nh3, 200, 300)
    draw.text((13, Y_GAS), f"Ox:{ox:.0f}k",  font=FONT_S, fill=c_ox)
    draw.text((62, Y_GAS), f"Rd:{rd:.0f}k",  font=FONT_S, fill=c_rd)
    draw.text((111,Y_GAS), f"N3:{nh3:.0f}k", font=FONT_S, fill=c_nh3)
    draw_hbar(draw, 13,  Y_GAS + 10, 44, 2, min(ox  /  60, 1.0), c_ox)
    draw_hbar(draw, 62,  Y_GAS + 10, 44, 2, min(rd  / 600, 1.0), c_rd)
    draw_hbar(draw, 111, Y_GAS + 10, 44, 2, min(nh3 / 400, 1.0), c_nh3)
    draw.line((0, 39, W, 39), fill=SEP)

    # ── PM row ────────────────────────────────────────────────────────────────
    icon_dust(draw, 2, Y_PM + 2, DIM)
    c_p1  = qcolor(pm1,  12, 35)
    c_p25 = qcolor(pm25, 12, 35)
    c_p10 = qcolor(pm10, 25, 50)
    draw.text((13, Y_PM), f"1:{pm1:.0f}",    font=FONT_S, fill=c_p1)
    draw.text((62, Y_PM), f"2.5:{pm25:.0f}", font=FONT_S, fill=c_p25)
    draw.text((111,Y_PM), f"10:{pm10:.0f}",  font=FONT_S, fill=c_p10)
    draw_hbar(draw, 13,  Y_PM + 10, 44, 2, min(pm1  / 50, 1.0), c_p1)
    draw_hbar(draw, 62,  Y_PM + 10, 44, 2, min(pm25 / 50, 1.0), c_p25)
    draw_hbar(draw, 111, Y_PM + 10, 44, 2, min(pm10 / 50, 1.0), c_p10)
    draw.line((0, 52, W, 52), fill=SEP)

    # ── Light + AQ row ────────────────────────────────────────────────────────
    icon_sun(draw, 2, Y_AQ + 1, CYAN)
    draw.text((13, Y_AQ + 1), f"Lux:{int(lux)}", font=FONT_S, fill=CYAN)
    draw.text((75, Y_AQ + 1), f"P:{pres:.0f}",   font=FONT_S, fill=DIM)
    label, badge_col = aq_info(pm25)
    draw.rectangle((119, Y_AQ, W-2, Y_AQ + 10), fill=badge_col)
    draw.text((121, Y_AQ + 1), label, font=FONT_S, fill=BG)
    draw.line((0, 64, W, 64), fill=SEP)

    # ── Dual sparkline: temperature (left) | PM2.5 (right) ───────────────────
    mid = SPARK_W
    draw.text((1,      Y_SPARK), "T\u00b0F",  font=FONT_S, fill=DIM)
    draw.text((mid+2,  Y_SPARK), "PM2.5",     font=FONT_S, fill=DIM)

    def draw_spark(hist, x0, col_fn):
        vals = list(hist)
        vmin, vmax = min(vals), max(vals)
        rng = max(vmax - vmin, 0.5)
        for i, v in enumerate(vals):
            norm = (v - vmin) / rng
            py = Y_SPARK + SPARK_H - 1 - int(norm * (SPARK_H - 2))
            draw.point((x0 + i, py), fill=col_fn(v))

    draw_spark(temp_hist, 0,       lambda v: temp_color(c2f(v)))
    draw.line((mid, Y_SPARK, mid, H-1), fill=SEP)
    draw_spark(pm25_hist, mid + 1, lambda v: qcolor(v, 12, 35))

    disp.display(img)


# ── Main loop ─────────────────────────────────────────────────────────────────
pm1 = pm25 = pm10 = 0.0

logging.info("Enviro+ dashboard starting")

while True:
    try:
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
            pms5003_sensor = PMS5003()

        temp_hist.append(temp_c)
        pm25_hist.append(pm25)
        tf = c2f(temp_c)
        draw_frame(tf, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10)
        write_mqtt(tf, hum, pres, lux, ox, rd, nh3, pm1, pm25, pm10)

        time.sleep(2)

    except KeyboardInterrupt:
        logging.info("Stopped by user")
        break
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        time.sleep(5)
