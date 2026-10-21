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
- 23:21 EDT: "Why do we need it? Why are we putting any project code or logic outside the project?"
- 23:23 EDT, on moving `raw_retention` into enviroplus: "Yes, move it"
- 23:21 EDT, on a separate Ruff formatting commit plus a pinned Ruff: "I agree with you"
- 23:29 EDT, on dropping the restart backoff for a flat restart: "I agree with your recommendation"

Executor: pi-claude, by operator assignment (AGENTS B).

## Plan as approved (pi-claude, 22:14 EDT)

1. **Tier 1:**
   - Every loop's reads are retained through the existing `raw_retention` (h; moved into enviroplus at 23:23, see below) as provider `local_sensors`, each driver's output exactly as returned.
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
  - Each day is first read through in full, so a corrupt or unverifiable record fails the replay before any row is touched.
  - Then the day's rows are deleted from the day's start and rewritten, streaming one interval at a time.
  - Rows from before the first read Tier 1 holds are never deleted, so the cutover interval keeps its live row.
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
  - Page taps: each rising edge of the LTR559 proximity past `display.tap_proximity`, with its reading and threshold. Per the operator at 23:11, "Can we make the proximity Tier 1 but only record events?", the 10 Hz polls themselves are not kept.
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
1. Install `sensirion-i2c-scd4x==1.1.0` into `/home/pistrommy/.virtualenvs/pimoroni`.
2. Fast-forward the enviroplus main checkout. The services run from it, and `CONFIG_PATH` points at its `dynamic_config.pi5.json`.
3. Run `systemctl daemon-reload` and restart `enviro_dash`, `ambient_wx`, `nws_wx` and `airnow_wx` one at a time, checking each.
   - All four `/etc/systemd/system/*.service` files are symlinks into the main checkout, so step 2 already installs their new content. That includes `enviro_dash`'s removed start limit.
   - The reload is what loads that content.
4. Check the live result:
   - The unit is active.
   - Tier 1 records are arriving under `raw-capture/local_sensors/`.
   - `readings` rows carry the SCD41 values.
   - Replaying a finished day reproduces the live rows, except around a process restart:
     - Live never writes the interval that was open at shutdown.
     - Live writes the interval open at restart from its post-restart reads only.
     - Replay writes both from all their reads.
   - The Grafana panels render.

**Volume:** about 1.1–1.2 kB per record, measured on a representative record (2026-10-20 22:45; the reviewer measured 1169 B). Taps add a few bytes only when one occurs. Every 2 s that is about 47–50 MB/day and about 17–18 GB/year, into a tree the existing backup lane already replicates. 206 GB were free on 2026-10-20.

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
| F8 | Proximity reads not kept | Closed: taps retained (operator, 23:11) |
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

## `raw_retention` moved into enviroplus (operator, 23:23)

**What moved:**
- A search of `~/projects` found every consumer of `shared.raw_retention` in enviroplus: three collectors, the dashboard, `local_sensors.py` and the backfill script.
- `shared`'s own PROJECT-CONFIG forbids moving consumer-specific code there. It already listed the module's `ENVIRO_RAW_ROOT` read as coupling to remove.
- So `raw_retention.py`, with the F5 fix, `days()` and its tests (`test_raw_retention_write_failure.py`, `test_raw_retention_root_key.py`), now lives in enviroplus. Every import is repointed.

**The removal:**
- `shared` branch `fix/retention-write-failure-surfaces` becomes the removal of the module and its tests (p).
- It lands after this branch. Nothing then imports it.
- This branch no longer depends on any `shared` change. The suite passes against the unchanged `~/projects/shared`: 264 passed.

**Power after the move:** dropping the `ftruncate` fails 3 tests.

## F5 folded: a failed Tier 1 write raises (operator, 22:38)

Shared and consumer changes:

| Repository | Change |
|---|---|
| `raw_retention.py` | `retain()`/`record_outcome()` raise `RetentionWriteError`; torn line truncated |
| enviroplus collectors | `retain()` no longer wrapped; loops re-raise |
| enviroplus dashboard | Its Tier 1 write raises before derivation |
| Collector and dashboard units | `OnFailure` on every failed exit; flat restart, no stop limit |

**Units** (operator, 23:29): each unit restarts at its existing flat spacing, 10 s for the collectors and 30 s for the dashboard.
- No stop limit: the systemd default of 5 starts per 10 s is never reached at that spacing. So a fault such as a full disk retries for as long as it lasts, and collection resumes within one interval of the cause being fixed.
- Repeat alerts are throttled by the alert service itself (`stocks` `alert_config` `repage_seconds`), not by the units.
- The backoff (`RestartSteps`/`RestartMaxDelaySec`) of b9acd31 is removed, and with it the E-R2 residual.
- Neither restart nor backoff finds or fixes a root cause. The cause is in the journal, as the raised OS error. Correcting it is manual.
- **Change to a prior decision:** this replaces `enviro_dash.service`'s 120 s/2 start limit, set PROVISIONAL in the 2026-10-11 display repair. Under it, one full-disk event would have stopped the dashboard for good.

**Practice adopted:** write-ahead, then derive only from what is stored, report the write's own outcome, and alert through a watched channel. `docs/reviews/raw-retention-write-failure.md` has the reasoning and why no retry buffer was added. It moved here from `shared` with the module.

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

## Review: 8617150 + shared 1cdf41b (architecture-reviewer, Anthropic), dispositions

| # | Finding | Disposition |
|---|---|---|
| E1 | Replay never rebuilt the first interval | Closed: delete from interval start |
| E2 | Failed replay deleted rows | Closed: full validation pass first |
| E3 | Start limit stopped collection | Closed: backoff, no stop limit |
| E4 | 100 s derivation wrong | Closed: limit removed |
| E5 | Ambient/NWS loop re-raise untested | Disclosed; unchanged |
| S1–S3 | shared torn line, tests, dedup read | Closed in shared `1c37dc5` |

Power for the fixes, with the enviroplus suite at 253 passed against shared `1c37dc5`:

| Violation | Result |
|---|---|
| Delete bound at the first read | 1 failed |
| Cutover not protected | 1 failed |
| No full validation pass | 1 failed |

**Residual:** an error during a replay's writes leaves the rest of that day deleted.
- A transient SQLite error is repaired by rerunning the replay, because Tier 1 is untouched.
- A `derive_row` error repeats on every rerun until it is fixed. Live runs the same `derive_row` on the same records, so such a record would already have stopped live.

## Review: shared 1c37dc5 + enviroplus b9acd31 (architecture-reviewer, Anthropic), dispositions

Verdict: NO BLOCK on both.

| # | Finding | Disposition |
|---|---|---|
| E-R1 | Old-grid row survived a mid-day start | Closed: delete from the day's start |
| E-R2 | Backoff step never resets per fault | Closed: backoff removed (operator, 23:29) |
| E-R3 | `derive_row` error deletes rest of day | Residual reworded above |
| E-R4 | README replay bound stale | Closed |
| S-R1, S-R2 | fstat/append race; first-read cost | No defect |

**E-R2:** systemd counted restart steps from boot or the last manual start, not per fault. The backoff is removed instead.

**Proximity:** after the operator's 23:11 ruling, Tier 1 keeps tap events instead of every poll. Removing the tap recording fails 1 test. E-R1: restoring the interval-start bound fails 1 test. The suite gives 254 passed.

No further review round. The remaining classes are wording and operator-weighed residuals.

## Review

Six Anthropic architecture-reviewer rounds were run, the last on 1478c15: NO BLOCK.

**Provider families (k):** pi-claude itself can dispatch only Anthropic seats. An OpenAI-family seat was reachable through pi-codex, but was not requested: the operator assigned this work to pi-claude "while Codex is otherwise engaged". Whether to add it before landing is the operator's call.

**Round 6 (1478c15), dispositions:**

| # | Finding | Disposition |
|---|---|---|
| 1–4 | Move, reformat, taps, units | No defect |
| 5 | Deploy step 3 omitted `enviro_dash` and the symlinks | Closed |
| D1 | Write-failure record still described the backoff | Closed |
| D2 | Stale artifact path | Closed |
| P1 | Tests cannot tell which `raw_retention` copy is used | Residual until `shared` removes its copy |

**Also in round 6:**
- A reading exactly equal to `tap_proximity` is now in the tap test, which fails if `>=` becomes `>`.
- The deployed-effect review (d) follows landing.
