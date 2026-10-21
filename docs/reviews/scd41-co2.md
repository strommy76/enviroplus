# SCD41 and Tier 1 retention of local sensor reads

## Direction

Bryan, 2026-10-20, to pi-claude:

- 21:54 EDT: "research the required libraries and code to get the SCD-41 running and add them to the Enviro+ project"
- 21:56 EDT: "Can we create our own driver if necessary?"
- 21:59 EDT: "Yes, I agree iwth your plan with the Grafna panel folded in. You can work this while Codex is otherwise engaged"
- 22:03 EDT: "All changes need to comply with AGENTS.md"
- 22:07 EDT: "We always temperature and humidity values to be an upgrade over the Enviro+'s BME280 that's being influenced by the Pi heat generation. The SCD41 is located … approximately 7" above and outside the Pi where it should be uninfluenced"
- 22:11 EDT: "No, I would like all values to be stored. I didn't say that we should stop recording BME280 data. Also, can we refine the BME280 compensation using the SCD41? You can ingest the Enviro+ commits/PRs to understand what has been done in the past"
- 22:13 EDT: "We should ALWAYS be storing all raw data in a Tier 1 store! Derived (i.e. compensated) data goes in Tier 2"
- 22:15 EDT: "I approve the plan, and yes keep every read"
- 22:36 EDT, on F5: "Why does a failed write record success? Shouldn't success be determined after all writes are attempted? And shouldn't partial writes log success vs failure accurately? What is the optimal anti-fragile logic? What is generally accepted best practice?"
- 22:38 EDT, on pi-claude's recommendation: "no, fold it in"

Executor: pi-claude, by operator assignment (AGENTS B).

## Plan as approved (pi-claude, 22:14 EDT)

1. **Tier 1:**
   - Every loop's reads are retained through the existing `shared.raw_retention` (h) as provider `local_sensors`, each driver's output exactly as returned.
   - A failed read is recorded as that lane's error.
2. **Tier 2:** `readings` is derived from Tier 1 by one projection, used both live and by `--replay DAY`.
3. **Rows from before Tier 1:** kept as written, never rebuilt or dropped.
4. **SCD41:**
   - It is stored in both tiers.
   - It gets a CO₂ page and Grafana CO₂ panels.
   - Indoor temperature and humidity on the LCD and in Grafana come from the SCD41.
   - The BME280 keeps being recorded and plotted for comparison.
5. **Later, a separate change** refines the BME280 compensation:
   1. Check the SCD41 offset against the AcuRite reference.
   2. Fit the BME280 model from Tier 1.
   3. Replay the derived rows.
6. **Fixes from the 1c2eb9c review are carried in.** See the dispositions below.

## History ingested (for step 5)

| Commit | Model |
|---|---|
| `1f5379a` 2026-03-15 | CPU factor derived at startup |
| `21a0de1` 2026-03-16 | Magnus RH correction |
| `47f9dd6` 2026-07-30 | Constant 6.35 °C pedestal |

The `47f9dd6` measurement:
- It was taken against an offset-corrected AcuRite reference, on 5-minute means.
- The gap term was 0.57 °F across the natural range, below the BME280's 1.87 °F short-term wander.
- The proportional form was "structurally wrong for the M.2-spaced mounting".

## What changed

**`local_sensors.py` (new)** holds the Tier 2 projection.
- `derive_row` builds one row per publish interval from that interval's Tier 1 records. The row is keyed by the interval's start time, in UTC.
  - Every lane takes its newest successful read in the interval.
  - A lane with no read in the interval is NULL.
  - It also applies `self_heat_offset_c` and the Magnus correction, both moved from `enviro_dash3.py`.
- `ensure_schema` creates the table or adds missing columns. It is additive only.
- `write` inserts through `shared.db_service.write_row` and never overwrites an existing row. Replay clears its span first, and a row from before Tier 1 that shares a key is kept.
- `replay` and the `--replay DAY...` command-line entry point rebuild each named day from Tier 1, on the current `publish_s` grid.
  - They delete that day's rows from its first retained read onward, then stream one interval at a time.
  - They also read the following day's file, only until its reads pass the day, because a read just before midnight is filed under the day it was retained.
  - Memory: a synthetic full day (43,200 records, 46 MB) replayed in 1.2 s at a 19 MB peak RSS.

**`enviro_dash3.py`:**
- `read_sample()` retains one record per loop, holding:
  - The BME280 reads, `bme_samples` of them.
  - The CPU temperature in raw sysfs millidegrees.
  - LTR559 lux.
  - MICS6814 resistance in ohms.
  - The checksummed PMS5003 frame as bytes, which keeps the particle counts and the atmospheric channels.
  - The SCD41 CO₂, temperature and RH.
  - `/proc` load, memory and uptime.
  - The LTR559 proximity reads polled between frames. They drive page taps, and the next record carries them.
- When a read opens a new publish interval, the finished interval becomes a `readings` row.
- The display uses the same projection.

**Calibration keys removed (p):** `cal_actual_f`, `cpu_hist_size` and `cpu_factor_override` come out, together with the startup-derived proportional model.
- That model is inert under `self_heat_offset_c`.
- Its startup calibration samples are not retained, so a row derived with it could not be rebuilt from Tier 1 (j).

**Other surfaces:**
- Config: `thresholds.co2_ppm`, from the UBA guide values.
- Grafana:
  - The Temperature and Humidity stats now read the SCD41.
  - The Temperature & Humidity series plots both the SCD41 and the BME280.
  - CO₂ has a stat panel and a time-series panel.
- README: a Data tiers section, the sensors, the schema and the compensation text.
- PROJECT-CONFIG: authority now reads Tier 1 = `raw_retention`, and every SQLite table is Tier 2.

## C / H declaration

**Lifetime:** permanent runtime code. k fires.

**Failure could be silent:** a wrong projection writes plausible values into `readings`.
- Tier 1 now makes `readings` rebuildable, so the projection itself can be corrected by replay.
- A read that was never retained is lost.

**Where failure surfaces (n):**
- A BME280, LTR559 or MICS6814 error ends the process, so the unit's Restart/OnFailure policy reports it.
- A PMS5003 or SCD41 error is recorded in Tier 1 as `partial` with the lane's error. That lane is NULL for the interval, and the dashboard logs a warning.
  - For the SCD41 that covers any `OSError`. `I2cError` subclasses it, and the transceiver's address ioctl raises a plain one.
- The SCD41 restarts measurement on the next loop after an error.
- A Tier 1 write failure raises `RetentionWriteError` (folded F5, see below). It ends the dashboard, and the weather and AirNow collectors, before anything is derived from the read. systemd restarts the unit, and persistent failure triggers `OnFailure`.

**Revert, forward-only (the 1c2eb9c F1 finding, adopted):**
- The previous code inserts 15 values by position. Against the widened table every write fails, and the unit ends up failed.
- So a rollback is forward: keep the named-column write and revert the behaviour instead.
- The columns stay, NULL where unwritten. No row is rewritten, and no column is dropped (j).

**Irreversible effects:**
- Three columns are added to `readings`.
- Tier 1 files are appended to and are never edited.

**Deploy order:**
1. Land `shared` `fix/retention-write-failure-surfaces` and fast-forward `~/projects/shared`. The enviroplus code imports its `RetentionWriteError`.
2. Install `sensirion-i2c-scd4x==1.1.0` into `/home/pistrommy/.virtualenvs/pimoroni`.
3. Fast-forward the enviroplus main checkout. The services run from it, and `CONFIG_PATH` points at its `dynamic_config.pi5.json`.
4. Install the changed `ambient_wx`, `nws_wx` and `airnow_wx` unit files and run `daemon-reload`. Then restart `enviro_dash`, `ambient_wx`, `nws_wx` and `airnow_wx` one at a time, checking each.
4. Check the live result:
   - The unit is active.
   - Tier 1 records are arriving under `raw-capture/local_sensors/`.
   - `readings` rows carry the SCD41 values.
   - Replaying a finished day reproduces the live rows, except around a process restart:
     - Live never writes the interval that was open at shutdown.
     - Live writes the interval open at restart from its post-restart reads only.
     - Replay writes both from all their reads.
   - The Grafana panels render.

**Volume:** about 1.1–1.2 kB per record before the proximity list, measured on a representative record (2026-10-20 22:45; the reviewer measured 1169 B). The proximity list adds about 20 small integers per record. Every 2 s that is about 50 MB/day and about 18 GB/year, into a tree the existing backup lane already replicates. 206 GB were free on 2026-10-20.

## Research (AGENTS C)

| Option | Finding |
|---|---|
| Sensirion `sensirion-i2c-scd4x` 1.1.0 | Vendor driver, 2025-07; chosen |
| Pimoroni `scd4x` 0.0.2 | Hard-codes `SMBus(1)`; 2023 |
| Own driver | Would duplicate the vendor implementation (h) |
| Adafruit CircuitPython SCD4x | Needs Blinka |

**Live check, 2026-10-20 21:58 EDT:**
- Serial `0xc6cb55073bf3`, variant SCD41, offset 4.00 °C, automatic self-calibration on.
- Readings: 442, 450 and 441 ppm, 24.0 °C, 48.6–49.7 % RH.

## Values (AGENTS g)

| Value | Source |
|---|---|
| 0x62 | Fixed SCD4x address |
| CRC-8 0x31 / init 0xFF | Sensirion datasheet and driver examples |
| Pressure × 100 | BME280 reports hPa; the driver takes Pa |
| CO₂ 1000 / 2000 ppm | UBA guide values, Bundesgesundheitsbl. 2008, 51:1358 |
| PMS words 0–2 | `PMS5003Data.pm_ug_per_m3(size)` default |
| Interval length | Existing `intervals.publish_s` |
| SCD41 temperature offset 4 °C | **PROVISIONAL**, factory default |

The SCD41 offset is settled by step 5's reference comparison, using Sensirion's formula: offset = T_SCD41 − T_ref + previous offset.

## Test power (AGENTS r)

The affected files run 55 tests. The full suite: 242 passed. Each violation below was made in the real implementation, run, and reverted:

| Violation | Result |
|---|---|
| PMS atmospheric words used | 2 failed |
| SCD41 gap filled with a value | 3 failed |
| Pedestal not subtracted | 1 failed |
| Tier 1 write removed | 3 failed |
| CO₂ trend gap hidden | 1 failed |
| Display not cleared after a silent interval | 1 failed |
| No SCD41 restart after an error | 1 failed |
| Indoor temperature taken from the BME280 | 1 failed |
| Migration skips the new columns | 1 failed |
| `partial` outcome lost | 1 failed |

**How the tests work:**
- They replace the hardware with stand-ins that return the drivers' shapes: a PMS frame as bytes, Sensirion `.value` signals, and `IOError`-based `I2cError`.
- The replay test rebuilds the live rows from Tier 1 and compares them to what live wrote.
- The humidity expectation is worked by hand from the Magnus formula. It is not copied from the implementation.

## Review: 1c2eb9c (architecture-reviewer, Anthropic), dispositions

| # | Finding | Disposition |
|---|---|---|
| F1 | Revert path crash-loops | Closed: forward-only revert declared |
| F2 | SCD41 error stops all lanes | Closed: lane error, restart |
| F3 | Display and migration untested | Closed: both tested, power observed |
| F4 | Deploy order undeclared | Closed: declared above |
| F5 | Extra 500 ms sleep | Closed: removed |
| F6 | CO₂ trend has no gaps | Closed: one point per interval, None kept |
| F7 | Suite count | Closed: counts re-measured |
| F8–F12 | No defect | No action |

The column list is now generated from the one `_COLUMNS` declaration in `local_sensors.py`, which addresses the reviewer's Axiom 2 note.

## Review: a522210 (architecture-reviewer, Anthropic), dispositions

| # | Finding | Disposition |
|---|---|---|
| F1 | Single-day replay ≠ live | Closed: interval key, next-day file read |
| F2 | Tests depend on wall clock | Closed: test clock starts at real time |
| F3 | Interval logic had no power | Closed: multi-read interval test |
| F4 | Restart mid-interval differs | Declared above; replay holds more reads |
| F5 | Failed Tier 1 write still derives | Raised to operator (D): shared code |
| F6 | README stale and contradicted | Closed |
| F7 | Cutover date asserted early | Closed: "first local_sensors record" |
| F8 | Proximity reads not kept | Closed: retained with the next record |
| F9 | SCD41 plain OSError escapes | Closed: lane catches OSError |

Power observed for the round-2 fixes. Each violation was made in the real implementation, and the full suite was run:

| Violation | Result |
|---|---|
| HAT lanes from the interval's first read | 1 failed |
| `last_with` picks the oldest read | 1 failed |
| BME280 not averaged | 1 failed |
| Humidity from the first BME280 sample | 1 failed |
| `ts` from read time | 2 failed |
| Next day's file not read | 1 failed |
| Next day's intervals included | 1 failed |
| Proximity not retained | 1 failed |

Full suite: 244 passed.

The test clock starts at the real time, because `raw_retention` files each record under the real UTC day. A test run that crosses UTC midnight mid-test could still split across two files. That window is a few seconds a day and is not guarded.

## Review: 6bee698 (architecture-reviewer, Anthropic), dispositions

| # | Finding | Disposition |
|---|---|---|
| R1 | publish_s reload overwrote a live row | Closed: open interval keyed on its own grid |
| R2 | Replay left old-grid/old-calibration rows | Closed: replay clears its span |
| R3 | Replay memory grew with days | Closed: streamed, 19 MB/day measured |
| R4 | In-place test could not fail | Closed: recalibration and grid replays |
| R5 | Restart statement incomplete | Closed: corrected in the docs |
| R6 | F8/F9 had no test power | Closed: call-counting and plain-OSError tests |
| R7 | `ts` meaning changes at cutover | Closed: documented; a colliding legacy row is kept |
| R8–R10 | No defect | No action |

**R1 simplification:** the reviewer offered "close when publish_s changes" as an alternative fix. It is not needed: a new grid renumbers the buckets, so the open interval closes anyway. A test of that alternative left the suite green (246 passed), so the extra check protected nothing.

Power observed. Each violation was made in the real implementation, and the full suite was run:

| Violation | Result |
|---|---|
| Open interval keyed on the new grid | 1 failed |
| Replay without the span delete | 1 failed |
| Proximity list not cleared | 1 failed |
| SCD41 lane catches only `I2cError` | 1 failed |
| Upsert, which overwrites a legacy row | 1 failed |

Full suite: 247 passed.

## F5 folded: a failed Tier 1 write raises (operator, 22:38)

Shared and consumer changes:

| Repository | Change |
|---|---|
| `shared` | `retain()`/`record_outcome()` raise `RetentionWriteError`, partial line truncated |
| enviroplus collectors | `retain()` no longer wrapped; loops re-raise |
| enviroplus dashboard | Its Tier 1 write raises before derivation |
| Collector units | `OnFailure` and a start limit (`100s`/2) |

**The start limit is PROVISIONAL.** It is the startup timeout of 90 s plus `RestartSec` 10 s, the same rule as `enviro_dash.service`.

**Practice adopted:** write-ahead, then derive only from what is stored, report the write's own outcome, and alert through a watched channel. The `shared` review artifact `docs/retention-write-failure-review.md` has the reasoning and why no retry buffer was added.

**Power observed,** with the enviroplus suite run against the `shared` branch (251 passed):

| Violation | Result |
|---|---|
| Ambient swallows the failure at `retain()` | 1 failed |
| NWS swallows the failure at `retain()` | 1 failed |
| Provider loop swallows the error | 1 failed |
| Dashboard swallows its Tier 1 failure | 1 failed |

The ambient and NWS loop-level re-raises have no test.

**The supported Ruff lane was red on `main` before this change** (AGENTS D, not acted on):
- `ruff check`: 38 findings.
- `ruff format --check`: 19 files.
- Ruff is not in the dashboard interpreter.

This branch removes one pre-existing finding in each of `enviro_dash3.py` and `tests/test_dash_loop.py`, and its new files are clean.

## Review

Pending: an Anthropic architecture-reviewer seat on the named revision. pi-claude can provision only Anthropic, so other provider families are unreachable from this seat (k).
