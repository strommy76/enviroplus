# SCD41 CO₂ sensor integration

## Direction

Bryan, 2026-10-20, to pi-claude:

- 21:54 EDT: "research the required libraries and code to get the SCD-41 running and add them to the Enviro+ project"
- 21:56 EDT: "Can we create our own driver if necessary?"
- 21:59 EDT: "Yes, I agree iwth your plan with the Grafna panel folded in. You can work this while Codex is otherwise engaged"
- 22:03 EDT: "All changes need to comply with AGENTS.md"

Executor: pi-claude, by operator assignment (AGENTS B).

## Plan

1. Dependency: `sensirion-i2c-scd4x==1.1.0`, the vendor driver.
2. `enviro_dash3.py`:
   - Start periodic measurement on the existing I2C bus.
   - Read a sample only when the sensor reports it ready.
   - Feed the BME280 pressure to the sensor's pressure compensation.
3. `readings`:
   - New columns `co2_ppm`, `scd41_temp_c` and `scd41_rh`, stored as the driver reports them.
   - A publish interval with no new sample stores NULL, never a repeat.
4. Display: a new CO₂ page, colored by `thresholds.co2_ppm`.
5. Grafana: a CO₂ stat panel and a CO₂ time series on the Enviro+ dashboard.
6. Tests with observed power. Then one review, the supported validation, the operator's landing verdict, and deployment with a live check.

Out of scope: calibration changes. The sensor keeps its factory settings: 4 °C temperature offset, automatic self-calibration on, no persisted settings.

## C / H declaration

**Lifetime:** permanent runtime code, so it carries full rigor before its second run.

**Failure could be silent:**
- A wrong column mapping, a stale sample re-stored, or a wrong pressure unit would write plausible but wrong values into the authoritative, append-only `readings` table.
- So k fires: this branch and this review artifact, one independent review, and the operator's verdict.

**Where failure surfaces (n):**
- Any SCD41 I2C error ends the process. The unit's Restart/OnFailure policy reports it, the same policy every non-PMS5003 sensor already follows.
- A sensor that never reports data ready stores NULL, and the display shows "--" after one publish interval.

**Revert:**
- Revert the branch merge and restart `enviro_dash.service`.
- The three added columns stay in the table. They are NULL on rows written before the change and after a revert.
- Nothing is rewritten.

**Irreversible effects:** none. `ALTER TABLE ADD COLUMN` is additive, and no existing row changes.

## Research (AGENTS C)

| Option | Finding |
|---|---|
| Sensirion `sensirion-i2c-scd4x` 1.1.0 | Vendor driver, 2025-07; chosen |
| Pimoroni `scd4x` 0.0.2 | Bus 1 hard-coded; 2023 |
| Own driver | Would duplicate the vendor implementation (h) |
| Adafruit CircuitPython SCD4x | Needs the Blinka compatibility layer |

**Sensirion `sensirion-i2c-scd4x` 1.1.0:**
- It implements the full SCD4x command set.
- It takes the I2C device path, so it honors the existing `I2C_BUS` binding.
- Cost: it pulls in pure-Python transitive packages the dashboard does not use: `sensirion-shdlc-*`, `pyserial` and `intelhex`, about 5.7 MB in total.

**Pimoroni `scd4x` 0.0.2:**
- `SCD4X.__init__` opens `SMBus(1)` itself, which ignores `I2C_BUS`.
- Its CRC error message names another part ("ICP10125").

**Live check on this host, 2026-10-20 21:58 EDT** (scratch install, sensor otherwise unused):
- Serial `0xc6cb55073bf3`, variant SCD41, temperature offset 4.00 °C, automatic self-calibration on.
- Three samples in 15 s: 442, 450 and 441 ppm, 24.0 °C, 48.6–49.7 % RH.

## Values (AGENTS g)

| Value | Source |
|---|---|
| 0x62 | Fixed SCD4x address (datasheet) |
| CRC-8 0x31 / init 0xFF | Sensirion datasheet and driver examples |
| 500 ms after stop | Datasheet `stop_periodic_measurement` execution time |
| Pressure × 100 | BME280 reports hPa; the driver takes Pa |
| CO₂ edges 1000 / 2000 ppm | UBA guide values, Bundesgesundheitsbl. 2008, 51:1358 |
| NULL after one silent interval | The existing `intervals.publish_s` |

The Grafana panels carry no color thresholds. The device's band lives once, in the dashboard config, and is not copied into a second source (Axiom 1).

## Test power (AGENTS r)

51 tests in the affected files, observed at the implementation revision. Each real violation below was made in the implementation, run, and then reverted:

| Violation | Result |
|---|---|
| Sample not cleared after write | 1 failed |
| Pressure passed in hPa | 1 failed |
| SCD41 temperature and RH columns swapped | 1 failed |
| No stop before start | 1 failed |
| CO₂ page dropped from `PAGES` | 1 failed |
| Config green edge 1000→1200 | 1 failed |

The full suite: 237 passed.

These tests replace the hardware with stand-ins that return the driver's own result shape: objects with `.value`. They do not prove I2C behavior. The live check above and the deployed check cover that.

## Discovery (AGENTS D, not acted on)

The supported Ruff lane is red on `main` (`d350673`) before this change:
- `ruff check`: 38 findings.
- `ruff format --check`: 19 files would be reformatted.
- Ruff is not installed in the dashboard's interpreter. 0.15.12 was used from the stocks venv.

This branch adds no new `ruff check` finding in the files it touches. The per-file counts on `main` and on the branch are equal: `enviro_dash3.py` 2/2, `tests/test_dash_loop.py` 1/1, and 0/0 in the other two files.

## Review

Pending: an Anthropic architecture-reviewer seat on the named revision. pi-claude can provision only Anthropic, so no other provider family is reachable from this seat. That is recorded here as k requires.
