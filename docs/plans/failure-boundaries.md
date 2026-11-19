## Current receiving-fold amendment — November19

Same lasting/silent/irreversible C/H increment, branches and review artifacts.
Pi09430141/94723643 accept the exact folds below for direct verification; no
new seat round unless the design grows. Current details, evidence, all-section
and axiom assessment are in failure-boundaries-review.md.

E1 retains shared BME/LTR and SCD bus ownership and closes both failed gas bus handles. E2 refits the actual between-arrival age, provisionally159.304253s; Ambient activation remains held. F4 removes duplicate producer env loading.

No new host policy follows the reboot; the blanket scheduling gate is withdrawn.
The current test-database owner must release it before this suite uses it.
Canonical, operator landing and deployed effect remain separate prerequisites;
older dated clearances below are provenance, not current clearance for these folds.

# Enviroplus: independent sensor capture and provider health

Authority: Bryan's November19 10:33 every-sensor isolation decision (6984c89c),
10:45/10:50 scope decisions (d0a26347/6a9f33b9), Pi0657f232 and3e34118d.
One change covers enviroplus#30 E1/E2 and the confirmed auditF4 backup-source
binding defect. Broad .env/config cleanup and future Stocks-host-move coupling
are deferred. No hardware re-enable before the actual HAT is reconnected.

## Declaration and sequence
Lasting runtime implementation. Failure CAN be silent (missing sensor/provider
observations or backing up an obsolete DB) and irreversible (missed raw reads;
legacy pre-retention rows have no reconstruction). Driver errors surface in the
retained acquisition record and journal; provider staleness has the existing
alert boundary; real storage failure still stops the writer loudly. Revert the
cohesive source/config/unit change for future behavior. Never reconstruct or
delete canonical/legacy data to make a check pass; Git cannot recover missed data.

Use one isolated branch/review artifact based on reviewed0350abe, leaving the
backup worktree frozen. Implementation/source checks may proceed now; no deploy
or heavy test while restore and its queued Stocks canonical run. Commit this
plan with the change, open one draft PR, run owning and canonical checks after
the resource gate. Implementation gets OpenAI+GLM family review through the
existing fleet interface, finding adjudication, then Pi's receiving review.
Landing, installed-effect acceptance and hardware activation remain distinct.

## Actual source and minimum change

E1 is confirmed directly: enviro_dash3 initializes display/SPI, I2C, BME280,
LTR559, PMS and SCD41 at import; some reads/taps/display calls also escape lane
handling. local_sensors.derive_row indexes BME/lux/gas/CPU unconditionally.
Existing cabled-read isolation is incomplete at construction/bus boundaries.

Extract hardware acquisition into one cohesive local sensor I/O module with lazy,
independent driver initialization/read boundaries, including the display hardware.
The existing enviro_screens renderer remains pure; no separate adapter file is added. The entrypoint composes these
owners with existing raw retention and projection; it is not another hardware
registry/plugin framework. Each real sensor (including host metrics) records
its own failed acquisition without invented measurements; siblings still read.
Proximity and display failures cannot terminate capture. A reconnected device
reinitializes through its driver on a later ordinary cycle, without a new retry
service/backoff tree. SCD41 can read without BME pressure compensation when BME
is absent; no replacement pressure is invented. Every available driver return
retains its present raw shape. Failed-only fields project NULL, never a stale
held value or another sensor's replacement. Local projection uses the existing
last_with seam for all nullable lanes. Storage/config failures remain real
process failures; no broad exception wrapper around retention or writes.

E2 is confirmed directly in complete Ambient/NWS/provider collector loops:
provider errors are retained/logged while processes continue; OnFailure alone
cannot detect their missing data. Search the existing health surfaces, then add
one small read-only provider-freshness owner and one native timer/service using
the existing alert template. Evaluate each configured lane independently;
record query failures and still evaluate siblings, exit nonzero for actual
missing/stale/unreadable data. Read timestamp and validity from existing provider
schemas/contracts, including Ambient console-only rows (a new timestamp with
no outdoor values cannot establish outdoor health) and AirNow's provider-local
observation time. Do not add a second acquisition log, watchdog DB or per-provider
monitor service. Derive cadence and stale bounds from existing provider settings,
documented update times and retained healthy intervals; provisional values name
the settling measurement at definition. Do not invent a fixed multiplier or
activate an unfitted threshold. Use the existing shared unit renderer; no new
scheduler or broad unit conversion.

F4 is confirmed directly: sqlite_backup.main reads the literal component
source_path while collectors read SQLITE_PATH. Bind SQLite capture and estimate
to that existing required host key through the existing environment owner,
then remove the superseded literal. Keep raw-tree source binding aligned with
its actual collector owner if the current source read confirms the same defect;
do not invent an environment key for an unconfirmed path. The common backup
engine retains its opaque producer contract. A config binding edit must capture
the newly selected real scratch DB, not keep successfully verifying the old one.
No live .env edit until an actual required binding is known; any needed edit is
covered by effort-instance authority1cb01280 with backup/mode600/keys-only record.

## Premise and verification
Inputs read: complete enviro_dash3, local_sensors, sqlite_backup, Ambient/NWS/
provider collector loops, AirNow contract, dynamic_config.pi5 and PROJECT-CONFIG
at0350abe; shared renderer5830f0e; full issue30 and audit report. The deployed
CONFIG_PATH remains a host fact, not inferred from a tracked profile name.
Driver-specific APIs/timing must be checked against the installed supported
libraries before moving initialization, not reimplemented. Existing SQLite read-only
and snapshot interfaces remain owners; no migration/replay accompanies this change.

Tests inject a real-driver-producible initialization/read failure at each sensor
and display boundary, then observe sibling raw records and derived rows through
the real capture/projection seam. Reinserting fatal propagation must make the
owning test fail. Missing lanes produce NULL; genuine storage-write failures
must still raise. Use synthetic SQLite/retention inputs, never production writes.
Provider monitor tests exercise actual missing/stale/partial rows and one failing
query with healthy sibling results. F4 uses two distinct real SQLite DB files and
an environment-only source change through the public producer. Full canonical
pytest/Ruff follow the resource gate; real hardware/installed timer/alert effects
are separate deployment evidence. An unavailable HAT is recorded, not simulated
as a successful hardware validation.

## Construction axiom-check

| Axiom / falsification question | Prospective assessment |
|---|---|
|1 Truth: can an error/stale value or old DB be asserted as a current observation? | CONFORMS: preserve irreducible reads/errors; NULL absent values; bind backup to the collector's authoritative host key. |
|2 Cognition: is driver/provider discovery replaced by a curated fact roster? | CONFORMS: hardware drivers own their protocols; configured measurement roles are policy, provider schemas/contracts own interpretation; no discovery registry added. |
|3 Antifragility: can a single device/display/provider failure stop independent capture? | CONFORMS: independent lazy device boundaries and per-lane health results; storage remains a true shared dependency. |
|4 KISS: does a mechanism protect an absent use case? | CONFORMS: observed LTR failure stopped all capture; provider outage history and literal backup path are live cases. One monitor/clock, existing retention/alert owners. |
|5 Boundaries: is failure swallowed to look healthy? | CONFORMS: per-sensor retained errors/journal, provider nonzero health, real store failure propagated. |
|6 Maintenance: does the change grow the dashboard gravity well or duplicate derivation? | CONFORMS: extract hardware/display I/O and health; reuse raw retention, last_with and the one projection/live-replay path. |
|Preamble | CONFORMS: isolation replaces fatal shared startup; one independent monitor closes observed indefinite silent outages. No broad .env migration, speculative watchdog or new data store. |

A/B dated relays/executor; C/H above; D only directed E1/E2/F4 and required
consumers; E raw/deployed evidence over tests; F no secret values; G no live
activation during recovery; a–c minimum/enduring owners; d/e/f one cohesive
increment, distinct effect, operator landing; g derive/label thresholds;
h reuse driver/retention/projection/backup seams; i actual fatal coupling and
wrong-source causes; j raw/legacy authority preserved and projections rebuildable;
k declared family review then receiving review; l absent hardware/measurement
explicit; m same acquisition contract under missing hardware; n/o explicit
failures/dispositions; p/q remove fatal design statements/superseded paths and
update tests/docs; r real implementation violations observed, no mirrored oracle.

## Plan-review adjudication and implementation shape

PiClaude accepted November19 11:07 (`ac12a55e`) with minimum-structure and
net-source-line reporting constraints. One `sensor_io.py` owns hardware and
independent resource lifetimes; no separate display-adapter file/framework was
added. Keeping retryable driver/display handles out of the interval/retention
entrypoint removes its existing gravity well; the one owner also preserves PMS
GPIO handles across serial reinitialization. The installed gas driver latches
an absent ADC; its public availability/cleanup plus module reload resets that
failed setup for a later normal read, without writing driver-private flags.
The exact installed driver APIs were read before moving them.

`provider_health.py` is one read-only SQLite checker over committed freshness
obligations. Ambient's presence predicate comes from the collector's existing
measurement roles, including console-only rows. AirNow local timestamps must
agree with their recorded timezone abbreviation under the configured civil
zone, including the repeated autumn hour. The units are derived with the shared
renderer from `config/provider_health.json`; nested templates avoid changing the
backup renderer's existing single-template discovery contract. No health store,
second log, timer per provider, new .env key or service activation is introduced.

All current-day retained Ambient records were inspected through the supported
reader/classifier. Its first observation is left-censored (Nov18 21:59 UTC),
repeated up to46792s old: outage evidence, never a healthy freshness allowance.
194 newly advancing observations had maximum first-arrival age84.006878s;
159.006878s adds the actual60s poll and15s request budget. NWS reuses its7200s
admission plus600s poll/15s request; AirNow combines documented hourly granularity
and approximate one-hour publication lag with actual1800s poll/15s request.
These fitted/derived bounds remain provisional at definition with their settling
measurements. The E2 source reads actual latest observations, not log activity.

The live ENVIRO_RAW_ROOT key is absent; collectors use their declared repository
raw-capture root, matching backup configuration. The conditional raw-path concern
is closed without change from that source check; no new key/resolver is needed.
F4 removes the obsolete DB literal and invokes the existing environment owner.
The backup test deliberately leaves an obsolete literal pointing at its first
scratch DB, then changes only SQLITE_PATH: both captures must follow the binding.

Operator evidence November19 11:25 (source: broker648ab3e1, PiClaude sent11:25:55):
Bryan identified the preceding Ambient outage as a breaker trip caused by the
entryway light shorting in rain, restored about06:00 EST. This confirms the old
returns are off-nominal outage samples to exclude from the nominal fit, and the
real stopped-controller condition E2 must surface. This is a recorded decision,
not a verbatim quotation; the original relay travels with the review inputs.
