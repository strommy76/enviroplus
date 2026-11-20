# Receiving review: stocks #346 @5f839d6, enviroplus #31 @68176b5 (pi-claude-peer, 2026-11-19 12:44 EST)

Seats: GLM (glm-review.md): DON'T BLOCK on both. Opus architecture-reviewer (report returned as text; its scratch evidence is at scratchpad/scripts/fdleak.py): DON'T BLOCK #346, BLOCK #31.

| Finding | Status | Disposition |
|---|---|---|
| E1-1: re-initialising a failed I2C device opens a new bus fd on every failure; smbus2 and the Sensirion transceiver have no finalizer, so one absent sensor exhausts fds (limit 1024) and takes down siblings and the storage writer | CONFIRMED (Opus executed a construction: 4 to 204 fds over 200 cycles; pi-claude verified that smbus2 has close() and no __del__) | Fold, blocking #31: one smbus2.SMBus per SensorIO passed to BME280/LTR559 (`i2c_dev=`); keep the SCD connection and transceiver outside the device cache; close the failed ADS1015 bus before reload; one test proving the fd count stays flat across persistent failure through real smbus2 |
| E2-1: the Ambient bound is fitted to arrival lag (84 s), but the check measures now − MAX(ts) (gap plus lag); the author's own live read crossed it | CONFIRMED | Fold: refit to the quantity the check measures (max next-outdoor-arrival minus previous ts over a nominal window, excluding the breaker outage and wet-RF dropouts the operator identified). The Ambient lane is not activated until refitted |
| F4-1: duplicate environment load in sqlite_backup.py:97-98 | CONFIRMED | Fold: remove (shared backup_service already loads it) |
| S3-1: new FRED/attribution units `Wants=` capture, so a manual start enqueues a full capture and its OnSuccess chain | CONFIRMED (pull); harm UNCONFIRMED | Fold: keep After=, drop capture from Wants= in both |
| F10-1: isinstance(bool)/pd.isna guards and the "NaT"/None test params cover edits that do not occur | CONFIRMED (operator bare-bones rule) | Fold: drop both clauses and both params; keep the real fix (missing file fails; enabled requires a cutoff) |
| GLM: deadman _optional_int ValueError | REFUTED as a live input (systemd emits integers; verified live) | Closed, no action |
| GLM: lost gas ADC not re-setup after an established handle | CONFIRMED residual | Accepted per the author's adjudicated contract; the E1-1 gas fix handles the bus lifetime |
| GLM: cpu_temp ValueError; NWS/AirNow NULL renewal | UNCONFIRMED / out of scope | Closed, no action |

Verdict: #346 is accepted after the S3-1 and F10-1 folds (small; I verify them directly). #31 is blocked until the E1-1, E2-1 and F4-1 folds; I verify them directly, and a further seat round runs only if the fd-lifetime design changes beyond the stated correction.
Dependency (Opus): both PRs require shared code not yet on main, so the H1-H3 shared landing goes first.
