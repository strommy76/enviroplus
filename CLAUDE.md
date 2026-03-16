# Enviro+ Dashboard — Project Context

## What this is
Raspberry Pi Enviro+ air quality dashboard. Reads 10 sensors, displays on 160×80 ST7735,
publishes to Adafruit IO via MQTT, logs to SQLite. Repo: https://github.com/strommy76/enviroplus

## File header format
Python files use docstring block after shebang:
```
Path:        ~/projects/enviroplus/filename.py
Description: ...
Changelog:
  YYYY-MM-DD HH:MM:SS TZ  Description
```
JSON files use `_meta` key with `path`, `description`, `changelog` array.
Always append a new changelog entry when modifying a file.

## Config split
- `.env` — secrets and paths only (MQTT credentials, file paths). Never edit programmatically.
- `dynamic_config.json` — all tuning values. Hot-reloaded by running script within 2 seconds.
- Code — logic only, no magic numbers

## Key files
| File | Purpose |
|------|---------|
| `enviro_dash.py` | Main script — sensors, display, MQTT, SQLite |
| `dynamic_config.json` | Runtime config — thresholds, calibration, intervals |
| `enviro_dash.service` | systemd service definition |
| `enviro.db` | SQLite database (gitignored) |
| `enviro.log` | Rotating log file (gitignored) |

## Running
```bash
sudo systemctl status enviro_dash
tail -f ~/projects/enviroplus/enviro.log
```

## Linting
```bash
/home/pistrommy/.virtualenvs/pimoroni/bin/ruff check enviro_dash.py
```
Pre-commit hook runs automatically on staged `.py` files.

## Hardware
- Pi 3 B+ (home) — current host, BME280 reads high due to CPU heat
- `cal_actual_f` in `dynamic_config.json` corrects temperature; update when room temp changes
- Pi 5 (work) — planned migration target; will need recalibration

## Planned next
1. Review overnight SQLite data (cpu_temp_c vs temp_f correlation)
2. InfluxDB + Grafana on AI host — `docker/docker-compose.yml` stub ready
3. PMS5003 continuous polling thread (reduces sensor lag)
4. Adafruit SCD-41 CO₂ integration (I2C 0x62, no conflicts)
5. Migrate to Pi 5
