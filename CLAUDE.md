# Enviro+ Dashboard — Project Context

## What this is
Raspberry Pi Enviro+ air quality dashboard. Reads 10 sensors, displays on 160×80 ST7735,
logs to SQLite, displayed via Grafana. Repo: https://github.com/strommy76/enviroplus

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
- `.env` — secrets and paths only (provider API credentials, file paths). Never edit programmatically.
- `dynamic_config.json` — all tuning values. Hot-reloaded by running script within 2 seconds.
- Code — logic only, no magic numbers

## Key files
| File | Purpose |
|------|---------|
| `enviro_dash3.py` | **Active script** — AQM-345 layout, sensors, display, SQLite |
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
# Ruff is not currently installed in the pimoroni venv; the pre-commit
# referee named below does not exist. Reinstall before relying on it.
```
There is no pre-commit hook installed; `.git/hooks/` is empty.

## Hardware
- Pi 5 — current host. The Pi 3 migration completed 2026-07-30; the stack was
  reinstalled here rather than moved, which is why the derived tables predate
  this host's own collection history.
- BME280 reads high due to CPU heat; compensation is resolved in code from
  `dynamic_config.json` calibration values.

## Planned next
1. Review overnight SQLite data (cpu_temp_c vs temp_f correlation)
2. InfluxDB + Grafana on AI host — `docker/docker-compose.yml` stub ready
3. PMS5003 continuous polling thread (reduces sensor lag)
4. Adafruit SCD-41 CO₂ integration (I2C 0x62, no conflicts)
5. Migrate to Pi 5
