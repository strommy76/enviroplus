# 🌡️ Enviro+ Dashboard

A high-density, real-time air quality and environment monitor running on a Raspberry Pi with a [Pimoroni Enviro+](https://github.com/pimoroni/enviroplus-python) HAT. All 10 sensors displayed on a 160×80 ST7735 screen with color-coded bars, sparklines, and persistent SQLite logging.

---

## 🖥️ Display Layout

```
┌────────────────────────────────────────────────────────────────┐
│ ENVIRO+                                              9:45 PM   │  ← header
├────────────────────────────────────────────────────────────────┤
│ 🌡 72.3°F  ▓▓▓▓▓▓▓▓░░░░░░░   💧 H:49%  ▓▓▓▓▓░░░░░░░░░░░░   │  ← weather row
├────────────────────────────────────────────────────────────────┤
│ ☁  Ox:47k  ▓▓▓▓░░░  Rd:120k ░░░░░░░░  N3:158k ░░░░░░░░░░░   │  ← gas row
├────────────────────────────────────────────────────────────────┤
│ · ·PM1:2   ▓░░░░░░  2.5:3   ▓░░░░░░░  PM10:4  ▓░░░░░░░░░░   │  ← particulates
├────────────────────────────────────────────────────────────────┤
│ ☀ Lux:142   P:1013                              ┌ GOOD ┐       │  ← light + AQ
├──────────────────────────────┬─────────────────────────────────┤
│ T°F  ················        │ PM2.5  ·····················    │  ← sparklines
└──────────────────────────────┴─────────────────────────────────┘
```

**Color coding:**

| Color | Meaning |
|-------|---------|
| 🟢 Green | Normal / safe |
| 🟡 Yellow | Elevated / watch |
| 🟠 Orange | High / caution |
| 🔴 Red | Dangerous |
| 🟣 Magenta | Hazardous (PM2.5 > 150) |

---

## 🔬 Sensors

| Sensor | Chip | Measures | Notes |
|--------|------|----------|-------|
| Temperature | BME280 | °F (CPU-compensated) | Factor derived from `cal_actual_f` in `dynamic_config.json` |
| Humidity | BME280 | % RH | |
| Pressure | BME280 | hPa | |
| Light | LTR559 | Lux | Also used as proximity sensor |
| Oxidising gas | MICS6814 | kΩ (NO₂, O₃) | Higher resistance = cleaner air |
| Reducing gas | MICS6814 | kΩ (CO, VOCs) | Lower resistance = more pollution |
| Ammonia | MICS6814 | kΩ (NH₃) | Lower resistance = more pollution |
| PM1.0 | PMS5003 | µg/m³ | External particulate sensor |
| PM2.5 | PMS5003 | µg/m³ | Fine particles — primary AQI metric |
| PM10 | PMS5003 | µg/m³ | Coarse particles |

> 🔬 **Planned:** Adafruit SCD-41 breakout (CO₂, I2C 0x62) — no address conflict with existing sensors

---

## 🏗️ Architecture

```mermaid
flowchart LR
    subgraph Hardware
        BME280 -->|I2C| PI
        LTR559 -->|I2C| PI
        MICS6814 -->|I2C/ADC| PI
        PMS5003 -->|UART| PI
    end

    subgraph PI["Raspberry Pi"]
        enviro_dash.py
        dynamic_config.json
    end

    subgraph Outputs
        DISPLAY["🖥️ ST7735\n160×80 Display"]
        SQLITE[("🗄️ SQLite\nenviro.db")]
        MQTT["📡 Adafruit IO\n(MQTT)"]
        INFLUX[("📊 InfluxDB\n(planned)")]
        GRAFANA["📈 Grafana\n(planned)"]
    end

    dynamic_config.json -->|hot-reload| enviro_dash.py
    enviro_dash.py --> DISPLAY
    enviro_dash.py -->|every 60s| SQLITE
    enviro_dash.py -->|every 60s| MQTT
    INFLUX --> GRAFANA
    enviro_dash.py -.->|via Tailscale| INFLUX
```

---

## 📦 Hardware

| Component | Where to buy |
|-----------|-------------|
| [Pimoroni Enviro+](https://shop.pimoroni.com/products/enviro-plus) | Pimoroni |
| [PMS5003 Particulate Sensor](https://shop.pimoroni.com/products/pms5003-particulate-matter-sensor-with-cable) | Pimoroni |
| Raspberry Pi (3 B+, 4, 5, or Zero 2 W) | Various |
| [Adafruit SCD-41 CO₂ Sensor](https://www.adafruit.com/product/5190) | Adafruit *(planned)* |

---

## 🚀 Setup

### 1. Install Pimoroni libraries

```bash
git clone https://github.com/pimoroni/enviroplus-python
cd enviroplus-python
./install.sh
```

### 2. Clone this repo

```bash
git clone https://github.com/strommy76/enviroplus.git ~/projects/enviroplus
cd ~/projects/enviroplus
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure

```bash
cp .env.example .env   # add credentials — secrets only, no tuning values here
```

| Variable | Description |
|----------|-------------|
| `MQTT_BROKER` | MQTT broker hostname (default: `io.adafruit.com`) |
| `MQTT_USER` | Adafruit IO username |
| `MQTT_KEY` | Adafruit IO key |
| `SQLITE_PATH` | Path to SQLite database |
| `LOG_PATH` | Rotating log file path |
| `CONFIG_PATH` | Path to `dynamic_config.json` |

All tuning values (calibration, thresholds, intervals) live in `dynamic_config.json` — see below.

### 5. Run as a systemd service

```bash
sudo cp enviro_dash.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now enviro_dash
```

Check status:
```bash
sudo systemctl status enviro_dash
tail -f ~/projects/enviroplus/enviro.log
```

---

## ⚙️ dynamic_config.json

All tunable runtime values live here. The running script watches this file and **hot-reloads within 2 seconds** of any change — no restart needed.

```json
{
  "calibration": {
    "cal_actual_f": 74.4,   ← set to your reference thermometer reading
    "bme_samples":  3,       ← BME280 readings averaged per loop (reduces noise)
    "cpu_hist_size": 30      ← CPU temp history depth (~1 min of smoothing)
  },
  "intervals": {
    "publish_s":        60,  ← seconds between MQTT + SQLite writes
    "display_refresh_s": 2   ← display update rate
  },
  "thresholds": { ... },     ← color breakpoints for all sensors
  "display":    { ... }      ← bar graph scaling factors
}
```

**To recalibrate temperature:** just update `cal_actual_f` with your current reference thermometer reading and save. The script recalculates `CPU_FACTOR` automatically.

---

## 🌡️ CPU Temperature Compensation

The BME280 sits millimetres from the Pi's CPU and reads several degrees high. The script auto-derives a correction factor at startup (and on config hot-reload) from a known reference:

```
CPU_FACTOR = (cpu_temp - raw_temp) / (raw_temp - actual_temp)
compensated = avg(N raw samples) - (avg_cpu - avg_raw) / CPU_FACTOR
```

The log confirms the calibration on each startup:

```
2026-03-15 22:54:51 INFO  CPU_FACTOR=1.80 (raw=98.4°F  cpu=61.0°C  actual=74.4°F)
```

> 💡 The Pi 5 with active cooling runs significantly cooler than the 3 B+, so `CPU_FACTOR` will be much smaller — possibly close to 0.

---

## 🗄️ SQLite Schema

```sql
CREATE TABLE readings (
    ts          TEXT PRIMARY KEY,   -- local time: "2026-03-15 21:30:00"
    temp_f      REAL,
    humidity    REAL,
    pressure    REAL,
    lux         REAL,
    oxidising   REAL,
    reducing    REAL,
    ammonia     REAL,
    pm1         REAL,
    pm25        REAL,
    pm10        REAL,
    cpu_temp_c  REAL,               -- Pi CPU temperature (°C)
    cpu_load    REAL,               -- 1-minute load average
    mem_free_mb REAL,               -- available memory (MB)
    uptime_s    INTEGER             -- system uptime (seconds)
);
```

Query example — correlate CPU temp with sensor drift:
```sql
SELECT ts, temp_f, cpu_temp_c, cpu_load
FROM readings
WHERE ts >= '2026-03-15 22:00:00'
ORDER BY ts;
```

---

## 📡 Live Dashboard

**Adafruit IO:** https://io.adafruit.com/strommy/dashboards/bsenviropi

---

## 🔗 Upstream Sources

| Resource | Link |
|----------|------|
| Pimoroni Enviro+ Python library | https://github.com/pimoroni/enviroplus-python |
| PMS5003 Python library | https://github.com/pimoroni/pms5003-python |
| LTR559 Python library | https://github.com/pimoroni/ltr559-python |
| Pimoroni Enviro+ product page | https://shop.pimoroni.com/products/enviro-plus |
| Pimoroni learning: Enviro+ | https://learn.pimoroni.com/article/getting-started-with-enviro-plus |
| MICS6814 datasheet | https://www.sgxsensortech.com/content/uploads/2015/02/1143_Datasheet-MiCS-6814-rev-8.pdf |
| PMS5003 datasheet | https://www.aqmd.gov/docs/default-source/aq-spec/resources-page/plantower-pms5003-manual_v2-3.pdf |
| Adafruit SCD-41 guide | https://learn.adafruit.com/adafruit-scd-40-and-scd-41 |

---

## 📋 Roadmap

- [x] 10-sensor dashboard on ST7735 display
- [x] CPU temperature compensation with auto-derived factor
- [x] MQTT publish to Adafruit IO
- [x] SQLite logging with local timestamps + Pi telemetry
- [x] Rotating log file
- [x] systemd service with auto-restart
- [x] `dynamic_config.json` — hot-reloadable config, single source of truth
- [x] BME280 averaging + CPU history smoothing for noise reduction
- [x] Ruff linting with pre-commit hook
- [ ] Adafruit SCD-41 CO₂ sensor integration
- [ ] InfluxDB writer (stub in code, pending Docker setup)
- [ ] Grafana dashboard on AI host via Tailscale
- [ ] Migrate to Raspberry Pi 5
