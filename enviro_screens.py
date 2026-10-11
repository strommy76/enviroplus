#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        enviro_screens.py
PATH:        ~/projects/enviroplus/enviro_screens.py
DESCRIPTION: Pages for the Enviro+ 160x80 ST7735 LCD, drawn from a plain state
             dict. No hardware access: enviro_dash3.py supplies the state and
             sends the image to the display, so every page renders the same
             way under test as on the device.

             Pages: Glance (AQI gauge, indoor, outdoor), Air (PM1/PM2.5/PM10),
             Outside (Ambient station wind, UV, rain), Gas (MICS6814 channels).

             A value of None means the lane is absent or failed. It is drawn as
             "--" and leaves a gap in its trend line; it is never drawn as zero.

CHANGELOG:
2026-10-11 15:10      Claude      [Feature] Initial four-page layout; EPA AQI
                                      on the 2024 PM2.5 breakpoints.
--------------------------------------------------------------------------------
"""

import math
from importlib.resources import files

from PIL import Image, ImageDraw, ImageFont

W, H = 160, 80

_FONT_PATH = str(files("font_roboto.files").joinpath("Roboto-Medium.ttf"))
_fonts = {}


def _font(px):
    if px not in _fonts:
        _fonts[px] = ImageFont.truetype(_FONT_PATH, px)
    return _fonts[px]


# ── Palette ────────────────────────────────────────────────────────────────────
BG     = (6, 8, 14)
SEP    = (26, 30, 46)
DIM    = (80, 88, 112)
WHITE  = (236, 240, 248)
GREEN  = (40, 215, 75)
YELLOW = (235, 195, 0)
ORANGE = (255, 125, 0)
RED    = (255, 45, 45)
PURPLE = (148, 0, 211)
MAROON = (126, 0, 35)
CYAN   = (0, 215, 195)
BLUE   = (80, 150, 255)
AMBER  = (255, 170, 40)
MAGENTA = (205, 45, 205)

# ── EPA AQI ────────────────────────────────────────────────────────────────────
# (C_lo, C_hi, AQI_lo, AQI_hi). Federal regulatory constants: 40 CFR Part 58,
# Appendix G, as revised by the PM NAAQS final rule of 7 Feb 2024 (89 FR 16202),
# which lowered the PM2.5 Good/Moderate edge to 9.0 ug/m3 and reshaped the
# upper bands. The PM10 table was not changed by that rule.
PM25_BREAKPOINTS = (
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),
)
PM10_BREAKPOINTS = (
    (0, 54, 0, 50),
    (55, 154, 51, 100),
    (155, 254, 101, 150),
    (255, 354, 151, 200),
    (355, 424, 201, 300),
    (425, 604, 301, 500),
)
# EPA category per AQI band edge, in the same order as the breakpoint rows.
AQI_CATEGORIES = (
    (50, "GOOD", GREEN),
    (100, "MODERATE", YELLOW),
    (150, "SENSITIVE", ORANGE),
    (200, "UNHEALTHY", RED),
    (300, "V UNHEALTHY", PURPLE),
    (500, "HAZARDOUS", MAROON),
)
# Gauge full scale: the Unhealthy/Very Unhealthy edge. Above it the arc is full
# and the category name carries the severity.
GAUGE_FULL_AQI = 200


def aqi_sub(c, breakpoints):
    """EPA sub-index for one pollutant: linear interpolation within the band
    holding `c`. Callers truncate `c` to the table's precision first."""
    if c is None:
        return None
    for c_lo, c_hi, a_lo, a_hi in breakpoints:
        if c <= c_hi:
            return round((a_hi - a_lo) / (c_hi - c_lo) * (c - c_lo) + a_lo)
    return breakpoints[-1][3]


def pm_aqi(pm25, pm10):
    """AQI = the larger of the PM2.5 and PM10 sub-indices; None if neither.
    EPA truncates PM2.5 to 0.1 ug/m3 and PM10 to 1 ug/m3 before the lookup,
    which is what makes the gaps between table rows (9.0 -> 9.1) unreachable."""
    subs = [s for s in (
        aqi_sub(None if pm25 is None else math.floor(pm25 * 10) / 10, PM25_BREAKPOINTS),
        aqi_sub(None if pm10 is None else math.floor(pm10), PM10_BREAKPOINTS),
    ) if s is not None]
    return max(subs) if subs else None


def aqi_category(aqi):
    """(name, color) for an AQI value; ('NO DATA', DIM) when absent."""
    if aqi is None:
        return "NO DATA", DIM
    for edge, name, color in AQI_CATEGORIES:
        if aqi <= edge:
            return name, color
    return AQI_CATEGORIES[-1][1:]


# ── Threshold colors (bands from dynamic_config.json "thresholds") ─────────────
def band_color(value, band):
    """Green inside the green band, yellow inside the yellow band, else orange."""
    if value is None:
        return DIM
    if band["green_min"] <= value <= band["green_max"]:
        return GREEN
    if band["yellow_min"] <= value <= band["yellow_max"]:
        return YELLOW
    return ORANGE


def gas_color(channel, kohm, thresholds):
    """Severity of one MOS channel. Oxidising: higher resistance = more NO2.
    Reducing and NH3: lower resistance = more gas."""
    if kohm is None:
        return DIM
    if channel == "oxidising":
        t = thresholds["oxidising_k"]
        return GREEN if kohm <= t["green_max"] else YELLOW if kohm <= t["yellow_max"] else RED
    t = thresholds["reducing_k" if channel == "reducing" else "ammonia_k"]
    return GREEN if kohm >= t["green_min"] else YELLOW if kohm >= t["yellow_min"] else RED


# ── Primitives ─────────────────────────────────────────────────────────────────
def _text(d, xy, s, px, fill, anchor="la"):
    d.text(xy, s, font=_font(px), fill=fill, anchor=anchor)


def _fmt(v, spec):
    return "--" if v is None else format(v, spec)


def sparkline(d, values, x, y, w, h, color, lo=None, hi=None):
    """Area-filled trend. None values break the line. Draws nothing until two
    real points exist; the newest real point gets a marker."""
    pts = [v for v in values if v is not None]
    if len(pts) < 2:
        return
    lo = min(pts) if lo is None else lo
    hi = max(pts) if hi is None else max(hi, max(pts))
    span = (hi - lo) or 1.0
    step = (w - 1) / max(len(values) - 1, 1)
    fill = tuple(int(c * 0.25) for c in color)
    run, last = [], None
    for i, v in enumerate(list(values) + [None]):
        if v is None:
            if len(run) >= 2:
                d.polygon(run + [(run[-1][0], y + h - 1), (run[0][0], y + h - 1)], fill=fill)
                d.line(run, fill=color)
            run = []
            continue
        p = (x + i * step, y + h - 1 - (min(max(v, lo), hi) - lo) / span * (h - 1))
        run.append(p)
        last = p
    if last is not None:
        d.ellipse((last[0] - 1.5, last[1] - 1.5, last[0] + 1.5, last[1] + 1.5), fill=WHITE)


def _trend_mark(d, x, y, rising, color):
    up = [(x, y + 5), (x + 6, y + 5), (x + 3, y)]
    down = [(x, y), (x + 6, y), (x + 3, y + 5)]
    d.polygon(up if rising else down, fill=color)


def _page_dots(d, index, count):
    for i in range(count):
        cx = W - 4 - (count - 1 - i) * 6
        d.ellipse((cx - 1.5, H - 4.5, cx + 1.5, H - 1.5), fill=WHITE if i == index else DIM)


# ── Pages ──────────────────────────────────────────────────────────────────────
def _glance(d, s):
    pm = s["pm"]
    aqi = pm_aqi(pm["pm25"], pm["pm10"])
    name, color = aqi_category(aqi)
    cx, cy, r = 37, 38, 32
    box = (cx - r, cy - r, cx + r, cy + r)
    d.arc(box, 135, 405, fill=SEP, width=6)
    if aqi is not None:
        d.arc(box, 135, 135 + 270 * min(aqi, GAUGE_FULL_AQI) / GAUGE_FULL_AQI, fill=color, width=6)
    _text(d, (cx, cy - 4), _fmt(aqi, "d"), 26, WHITE, "mm")
    _text(d, (cx, cy + 13), "AQI", 8, DIM, "mm")
    _text(d, (cx, cy + 31), name, 8, color, "mm")

    ind, t = s["indoor"], s["thresholds"]
    _text(d, (80, 3), "INDOOR", 8, DIM)
    _text(d, (80, 11), _fmt(ind["temp_f"], ".0f") + "°", 26, band_color(ind["temp_f"], t["temp_f"]))
    _text(d, (124, 13), _fmt(ind["humidity"], ".0f") + "%", 12, band_color(ind["humidity"], t["humidity"]))
    _text(d, (124, 28), _fmt(ind["pressure"], ".0f"), 9, DIM)

    d.line((80, 43, 156, 43), fill=SEP)
    out = s["outdoor"]
    _text(d, (80, 47), "OUT", 8, DIM)
    _text(d, (100, 44), _fmt(out and out["tempf"], ".0f") + "°", 14, AMBER)
    temps = [v for v in s["outdoor_temp_hist"] if v is not None]
    if out is not None and len(temps) >= 2:
        _trend_mark(d, 128, 49, temps[-1] >= temps[0], AMBER)
    _text(d, (137, 47), _fmt(out and out["humidity"], ".0f") + "%", 9, DIM)
    sparkline(d, s["outdoor_temp_hist"], 80, 63, 62, 12, AMBER)


def _air(d, s):
    pm, hist = s["pm"], s["pm_hist"]
    # One y-scale for all three rows so they compare; its floor is the PM2.5
    # Good/Moderate edge, so sensor noise in clean air stays near the baseline.
    hi = max([v for k in hist for v in hist[k] if v is not None] + [PM25_BREAKPOINTS[0][1]])
    rows = (("PM1", "pm1", CYAN), ("PM2.5", "pm25", None), ("PM10", "pm10", YELLOW))
    for i, (label, key, color) in enumerate(rows):
        y = 2 + i * 25
        if color is None:
            color = aqi_category(pm_aqi(pm[key], None))[1]
        _text(d, (3, y), label, 8, DIM)
        _text(d, (3, y + 7), _fmt(pm[key], ".1f"), 14, color)
        sparkline(d, hist[key], 46, y + 1, 108, 21, color, lo=0.0, hi=hi)
        if i < 2:
            d.line((3, y + 24, 156, y + 24), fill=SEP)
    _text(d, (3, H - 9), "µg/m³", 7, DIM)


def _outside(d, s):
    out = s["outdoor"]
    cx, cy, r = 30, 38, 26
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=SEP, width=2)
    for deg, label in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
        a = math.radians(deg - 90)
        _text(d, (cx + (r - 7) * math.cos(a), cy + (r - 7) * math.sin(a)), label, 7, DIM, "mm")
    # Calm air has no direction worth drawing; the station still reports one.
    if out is not None and out["winddir"] is not None and out["windspeedmph"]:
        a = math.radians(out["winddir"] - 90)
        tip = (cx + (r - 2) * math.cos(a), cy + (r - 2) * math.sin(a))
        left = (cx + 8 * math.cos(a + 2.6), cy + 8 * math.sin(a + 2.6))
        right = (cx + 8 * math.cos(a - 2.6), cy + 8 * math.sin(a - 2.6))
        d.polygon([tip, left, right], fill=BLUE)

    get = (lambda k: None) if out is None else out.get
    _text(d, (66, 3), "WIND", 8, DIM)
    _text(d, (66, 11), _fmt(get("windspeedmph"), ".0f"), 22, WHITE)
    _text(d, (94, 20), "mph", 8, DIM)
    _text(d, (118, 13), "G " + _fmt(get("windgustmph"), ".0f"), 11, BLUE)
    sparkline(d, s["wind_hist"], 66, 37, 90, 14, BLUE, lo=0.0)
    d.line((66, 55, 156, 55), fill=SEP)
    _text(d, (66, 59), "UV", 8, DIM)
    _text(d, (80, 57), _fmt(get("uv"), ".0f"), 12, YELLOW)
    _text(d, (100, 59), "RAIN", 8, DIM)
    _text(d, (122, 57), _fmt(get("dailyrainin"), ".2f") + '"', 10, CYAN)


def _gas(d, s):
    gas, hist, t = s["gas"], s["gas_hist"], s["thresholds"]
    _text(d, (3, 2), "GAS  kΩ", 8, DIM)
    rows = (("OX", "oxidising", YELLOW), ("RED", "reducing", CYAN), ("NH3", "ammonia", MAGENTA))
    for i, (label, key, color) in enumerate(rows):
        y = 13 + i * 22
        _text(d, (3, y + 4), label, 9, color)
        _text(d, (28, y + 2), _fmt(gas[key], ".0f"), 13, gas_color(key, gas[key], t))
        sparkline(d, hist[key], 62, y, 92, 18, color)


PAGES = (_glance, _air, _outside, _gas)


def render(page, state):
    """Draw page `page` (index into PAGES) from `state`; returns a W x H image."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    PAGES[page](d, state)
    _page_dots(d, page, len(PAGES))
    return img
