# 🌡️ Enviro+ Dashboard

A high-density, real-time air quality and environment monitor running on a Raspberry Pi with a [Pimoroni Enviro+](https://github.com/pimoroni/enviroplus-python) HAT. Five pages on the 160×80 ST7735 screen (indoor air, particulates, outdoor weather, gas, CO₂), changed by a wave over the proximity sensor, with persistent SQLite logging.

---

## 🖥️ Display Pages

`enviro_screens.py` draws each page; a hand over the LTR559 proximity sensor moves to the next one. Corner dots show which page is on.

| Page | Shows |
|------|-------|
| 1 · Glance | EPA AQI gauge (2024 PM2.5 table); indoor °F, humidity, pressure; outdoor °F and humidity from the Ambient station with trend |
| 2 · Air | PM1, PM2.5, PM10 in µg/m³ with trend lines on one shared scale |
| 3 · Outside | Wind direction, speed and gust; UV; daily rain (Ambient station) |
| 4 · Gas | Oxidising, reducing, NH3 sensor resistance in kΩ with trends |
| 5 · CO₂ | SCD41 CO₂ in ppm, colored by the UBA guide-value bands, with a trend |

A missing or failed reading shows `--` and leaves a gap in its trend; it is never drawn as zero. Outdoor values older than `display.outdoor_stale_s` show `--`.

**Color coding:** the AQI gauge and PM2.5 value use the EPA category colors (Good green, Moderate yellow, Unhealthy for Sensitive Groups orange, Unhealthy red, Very Unhealthy purple, Hazardous maroon). Indoor temperature, humidity and gas values use the green/yellow/orange (gas: red) bands in `thresholds`.

---

## 🔬 Sensors

| Sensor | Chip | Measures | Notes |
|--------|------|----------|-------|
| Room temperature | TMP119 | °F (from driver °C) | Supported Adafruit TMP117/TMP119 driver; no software calibration |
| Humidity | SCD41 | % RH as reported | Native temperature compensation calibrated against TMP119; no extra software correction |
| Pressure | BME280 | hPa | |
| Light | LTR559 | Lux | Also used as proximity sensor |
| Oxidising gas | MICS6814 | kΩ (NO₂, O₃) | Higher resistance = cleaner air |
| Reducing gas | MICS6814 | kΩ (CO, VOCs) | Lower resistance = more pollution |
| Ammonia | MICS6814 | kΩ (NH₃) | Lower resistance = more pollution |
| PM1.0 | PMS5003 | µg/m³ | External particulate sensor |
| PM2.5 | PMS5003 | µg/m³ | Fine particles — primary AQI metric |
| PM10 | PMS5003 | µg/m³ | Coarse particles |
| CO₂ | SCD41 | ppm | Adafruit breakout, I2C 0x62; photoacoustic NDIR, one sample per 5 s, BME280 pressure compensation |
| Diagnostic temperature, humidity | SCD41 | °C, % RH | Retained as reported; native calibration events are retained as `local_sensor_calibration`. Humidity supplies the room display; temperature remains diagnostic |

---

## 🏗️ Architecture

```mermaid
flowchart LR
    subgraph Hardware
        BME280 -->|I2C| PI
        LTR559 -->|I2C| PI
        MICS6814 -->|I2C/ADC| PI
        PMS5003 -->|UART| PI
        SCD41 -->|I2C| PI
        TMP119 -->|I2C| PI
    end

    subgraph PI["Raspberry Pi"]
        enviro_dash3.py
        ambient_wx.py
        nws_wx.py
        provider_collector.py
        dynamic_config.pi5.json
    end

    subgraph Canonical["Canonical tier"]
        RAW[("📥 raw-capture/\nprovider responses as received")]
    end

    subgraph Derived["Derived tier"]
        SQLITE[("🗄️ SQLite\nenviro.db")]
    end

    subgraph Outputs
        DISPLAY["🖥️ ST7735\n160×80 Display"]
        GRAFANA["📈 Grafana\n(container, reads enviro.db)"]
        OFFSITE[("☁️ Offsite backup\nverified by remote hash")]
    end

    dynamic_config.pi5.json -->|hot-reload| enviro_dash3.py
    enviro_dash3.py --> DISPLAY
    enviro_dash3.py -->|every 60s| SQLITE
    ambient_wx.py & nws_wx.py & provider_collector.py -->|response bytes| RAW
    ambient_wx.py & nws_wx.py & provider_collector.py -->|projected rows| SQLITE
    RAW -->|replay| SQLITE
    SQLITE --> GRAFANA
    RAW & SQLITE -->|daily| OFFSITE
```

---

## 📦 Hardware

| Component | Where to buy |
|-----------|-------------|
| [Pimoroni Enviro+](https://shop.pimoroni.com/products/enviro-plus) | Pimoroni |
| [PMS5003 Particulate Sensor](https://shop.pimoroni.com/products/pms5003-particulate-matter-sensor-with-cable) | Pimoroni |
| Raspberry Pi (3 B+, 4, 5, or Zero 2 W) | Various |
| [Adafruit SCD-41 CO₂ Sensor](https://www.adafruit.com/product/5190) | Adafruit |

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
| `SQLITE_PATH` | Path to SQLite database |
| `CONFIG_PATH` | Path to the dashboard config document (`dynamic_config.pi5.json`) |
| `NWS_API_BASE_URL` | NWS API base URL |
| `NWS_STATIONS` | Ordered NWS station identifiers; first fresh observation wins |
| `NWS_USER_AGENT` | NWS-required caller identification |
| `NWS_POLL_S` | NWS poll interval in seconds |
| `NWS_SHUTDOWN_CHECK_S` | NWS service shutdown check cadence in seconds |
| `NWS_MAX_OBSERVATION_AGE_S` | Maximum accepted NWS latest-observation age in seconds |
| `NWS_COLLECTION_LOOKBACK_S` | Bounded NWS observations query window in seconds |

All tuning values (hardware addresses, thresholds, intervals, display) live in the CONFIG_PATH document — see below.

### 5. Run as a systemd service

```bash
sudo systemctl link "$PWD/enviro_dash.service"
sudo systemctl enable --now enviro_dash
```

Check status:
```bash
sudo systemctl status enviro_dash
journalctl -u enviro_dash -f        # or tail -f enviro_dash.log; each service has its own <service>.log
```

Before using this deployment example, reconcile the unit's device bindings and
operations-alert template with the target host. Repository content does not select
the active hardware unit; prove that binding from the running service manager as
required by PROJECT-CONFIG.md. Preserve and compare an existing copied unit as
described in [the repair plan](docs/display-spi-repair.md). For the repaired display,
GPIO9 is DC; pi-config owns the `spi0-2cs,no_miso` firmware binding that frees it.

---

## ⚙️ Dashboard config (CONFIG_PATH)

All tunable runtime values live here. The running script watches this file and **hot-reloads within 2 seconds** of any change — no restart needed.

```json
{
  "intervals": {
    "publish_s":        60,  ← length of the interval each readings row covers
    "display_refresh_s": 2   ← display update rate
  },
  "thresholds": { ... },     ← color bands for temperature, humidity, gas and CO₂
  "display":    { ... }      ← proximity tap level, outdoor staleness
}
```

## 🌡️ Room measurement sources

TMP119 supplies room temperature; SCD41 supplies reported humidity and CO₂;
BME280 supplies pressure. Complete driver returns (including BME temperature/RH)
remain canonical diagnostic evidence. No BME self-heat offset or Magnus software
correction is active. SCD41's native temperature compensation was calibrated against
TMP119 on October31; actual old/new settings and API outcomes are canonical in
`local_sensor_calibration`. The capture loop never writes that offset automatically.
A failed cabled read is retained as a lane error;
its interval has NULL when no successful read exists. No other-sensor fallback.
LCD SCD41 freshness behavior is unchanged; missing current TMP119 reads show `--`.

The supported TMP constructor's startup/readiness behavior is used unchanged,
per Bryan's October 30 decision; no extra timer, watchdog or plausibility guard.
SCD41's native offset compensates both temperature and humidity; no second software
humidity correction is layered over its output. Temperature agreement alone does
not independently establish humidity accuracy. Historical reads remain unchanged.

Stop the old hot-reloading dashboard before deploying the paired code/config and
approved dependency update, then start the selected service. Removing old config
keys while the old executable still runs is not a valid deployment order.

---

## 🗃️ Data tiers

| Store | Tier | Contents |
|-------|------|----------|
| `raw-capture/local_sensors/<day>.ndjson` | 1, canonical | Every loop's reads, each as its driver returned it; a failed read is recorded as that lane's error |
| `readings` (SQLite) | 2, derived | One row per publish interval, projected by `local_sensors.derive_row` using current sensor roles |

Live and `local_sensors.py --replay DAY...` use the same current projection. Replay is an explicit historical rewrite, never part of this sensor-role rollout. Records without TMP119 yield NULL temperature, not reconstructed BME estimates; SCD RH is available only where retained. BME records keep their list shape: old multi-read lists and new single-read lists both project pressure from the last element. A row is keyed by its interval's start (rows from before Tier 1 are keyed by their write time), and replaying a day rewrites that day's rows, on the current `publish_s` grid. Replay a day once it has ended. Rows from before the first `local_sensors` record have no Tier 1 reads: they are kept as written and never rebuilt, dropped or overwritten. Live and replay differ only around a process restart: live never writes the interval open at shutdown and writes the one open at restart from its post-restart reads; replay writes both from all their reads.

---

## 📝 Data notes

Sensor-source era: existing rows are unchanged. Before the TMP119 rollout,
`temp_f`/`humidity` were BME280-derived estimates; afterward they use TMP119 and
reported SCD41 RH. Generic room labels do not claim historical TMP119 measurements.
The retired 6.35 °C offset was fitted July 30 against a reference for the then-current
mounting, with a stated remeasure-on-mounting-change requirement. Its complete dated
provenance/config and old projection remain at source revision `c2209a09`; a current
replay does not recreate those old semantics. Exact onset of bias after relocation
is not established here. No old row or canonical artifact is rewritten by rollout.

Known-bad spans in the historical `readings` table (derived since local Tier 1 began; older rows have no raw source). Rows are kept as written; these notes are how a reader knows to discount them.

| Span (UTC) | Columns | Issue |
|------------|---------|-------|
| 2026-07-30 → 2026-08-05 | `pm1`, `pm25`, `pm10` | ~85,000 PMS5003 read timeouts; the code of the time re-stored the last good values as fresh, so PM in this span is largely repeats. Fixed 2026-10-11 (failed reads now store NULL). |
| 2026-09-17 00:26 → 2026-10-11 12:48 | all | No rows: the dashboard could not start after kernel 6.18.50 claimed GPIO9 (fixed by pi-config `spi0-2cs,no_miso`). |

---

## 🗄️ SQLite Schema

```sql
CREATE TABLE readings (
    ts          TEXT PRIMARY KEY,   -- UTC: "2026-03-15 21:30:00"; interval start (write time before Tier 1)
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
    uptime_s    INTEGER,            -- system uptime (seconds)
    co2_ppm     REAL,               -- SCD41 CO2 (ppm); NULL when no sample that interval
    scd41_temp_c REAL,              -- SCD41 temperature (°C), as reported
    scd41_rh    REAL                -- SCD41 relative humidity (%), as reported
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
| Sensirion SCD4x Python driver | https://github.com/Sensirion/python-i2c-scd4x |
| UBA indoor CO₂ guide values (CO₂ display bands) | Bundesgesundheitsblatt 2008, 51:1358–1369 |

---

## 📋 Roadmap

- [x] 10-sensor dashboard on ST7735 display
- [x] TMP119 room temperature and reported SCD41 humidity
- [x] SQLite logging with UTC timestamps + Pi telemetry
- [x] Rotating log file
- [x] systemd service with auto-restart
- [x] Hot-reloadable dashboard config, single source of truth
- [x] Every local sensor read retained in Tier 1; `readings` derived and replayable
- [ ] Ruff linting with pre-commit hook (referee not installed)
- [x] Adafruit SCD-41 CO₂ sensor integration
- [ ] Grafana dashboard on AI host via Tailscale
- [ ] Migrate to Raspberry Pi 5
