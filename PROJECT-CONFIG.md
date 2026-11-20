# PROJECT-CONFIG.md — Enviroplus

This file contains only repository-specific authority. Portable agent doctrine is
loaded from the canonical `agent-config` materialization and takes precedence if
this file ever conflicts with it.

## Repository Responsibility

Enviroplus owns local environmental sensor display and collection, external
weather and air-quality collection, raw retention of local reads and provider responses, the
derived SQLite store (`readings` and the provider tables), and their backup lane.

## Authority and Persistence

- Provider response artifacts written through `raw_retention.py` are the
  canonical source for replayable external observations.
- Tier 1 (canonical) is `raw_retention.py`; every SQLite table is Tier 2 (derived):
  - Local sensor reads are canonical in `raw_retention.py` as provider
    `local_sensors`: `enviro_dash3.py` retains every loop's reads there first,
    as each driver returned them.
  - `readings` is derived from them by `local_sensors.derive_row`; live and
    `local_sensors.py --replay DAY...` use that one projection, so rows rebuild
    from retention under current roles. Records without TMP119 yield NULL room
    temperature; old BME multi-read lists still supply pressure. No automatic replay
    accompanies a source change. Rows from before the first `local_sensors` record have no retained reads:
    SQLite and its backups are their only copy, so they are never rebuilt or
    dropped. Known-bad spans are annotated (README "Data notes"), not edited.
  - `outdoor`, `nws_weather` and `epa_air_quality` are derived. Rows captured
    since retention began (2026-08-06) rebuild through each lane's `--replay`
    (`ambient_wx.py`, `nws_wx.py`, `provider_collector.py --contract ...`);
    backfill rows rebuild through `scripts/import_raw_to_derived.py` from the
    retained history files. Live rows from before 2026-08-06 have no retained
    response: SQLite and its backups are their only copy, so never rebuild
    these tables by dropping them.
- Uncommitted `CONFIG_PATH` selects exactly one dashboard configuration
  document. That selected document owns hardware addresses,
  thresholds, display behavior, and intervals. Repository content does not
  declare which profile is active on a host.
- Uncommitted `.env` owns secrets and host-specific infrastructure bindings.
- `config/backup.json` owns the database/raw-capture replication contract;
  `enviro_backup.service` invokes the shared backup CLI. Use
  `systemctl start enviro_backup.service` for a manual run, so the native service
  owner prevents overlap with the timer. Do not run a concurrent direct CLI.
  `sqlite_backup.py` owns SQLite capture/estimation from the collectors' required `SQLITE_PATH` and artifact-bound restore validation;
  raw files use the native tree input and shared filesystem estimate. Database backups
  include irreplaceable legacy rows and are protected as authoritative. Delivery/run/maintenance
  observations are append-only authority; payloads/caches and status views are derived.
- Tests must isolate the raw-retention root and must never write to the live
  canonical capture tree.

## Service Boundaries

- Room temperature is TMP119; humidity and CO2 are SCD41 as reported; pressure
  remains BME280. No BME self-heat correction is active. SCD41's native temperature
  compensation is calibrated against TMP119; existing canonical retention records
  the actual settings and API outcomes as `local_sensor_calibration`. Runtime capture
  never writes the offset automatically or layers a software correction over it.
- `sensor_io.py` owns lazy independent driver/display I/O; `enviro_dash3.py` owns capture scheduling and the canonical
  `local_sensors` retention; `local_sensors.py` owns the `readings` projection
  and its `--replay`.
- `ambient_wx.py` and `nws_wx.py` independently own their provider collection
  loops and canonical response capture; `--replay DAY...` re-derives their
  table from retention through the same mapping and write path live uses.
- Each service writes its own log file (`<service>.log` beside the code) and
  the journal; no two processes rotate one file.
- `provider_collector.py` executes one committed capture contract from
  `contracts/` (`provider_contract.py` defines the contract boundary); the
  AirNow lane is `contracts/airnow_current.json`. A provider API change is a
  contract edit. The derived row is keyed by the provider's stated observation
  time and follows the provider's latest statement; every statement is retained.
  `provider_collector.py --contract <c> --replay DAY...` is the supported path
  that re-derives a contract's derived table from canonical retention through
  the same projection and write path live uses.
- Unit policy templates describe the intended service content; service_units
  derives current files through the shared renderer and backup owner, using the
  rendering interpreter and config-root location. Which
  hardware-specific dashboard unit is active is host residue and must be proven
  from the running service manager, not inferred from this repository.
- Backup orchestration, native incremental delivery and retention use the shared backup service;
  provider collectors and the dashboard do not implement competing backup paths.

- `provider_health.py` checks the configured derived-observation freshness obligations in `config/provider_health.json`. It preserves independent lane errors and uses the existing operations alert. The local readings lane is active only for the natively enabled producer; disabled/not-installed is explicitly inactive. Generate all native units with `PYTHONPATH=.. python -m service_units`; the hardware dashboard remains independently out of service until reconnected.

## Supported Validation

Run from the repository root using the interpreter selected by the deployed
service or a developer environment satisfying `requirements.txt`, with the
sibling `shared` package available:

```bash
PYTHONPATH=.. python -m pytest
python -m ruff check .
python -m ruff format --check .
```

The native backup lane additionally requires the qualified executable:
`DUPLICACY_TEST_BINARY=/absolute/path/to/duplicacy PYTHONPATH=.. python -m pytest tests/test_sqlite_backup.py`.
Without that binding, native cases report skipped coverage, never a native pass.

The owned `tests/test_env_completeness.py` integration lane checks required bindings
against this repository's installed `.env` (the common Git checkout for worktrees);
it never reports secret values. Missing bindings fail at the public config seam.

If Ruff is unavailable, that validation lane is red until the declared developer
environment is restored; absence is not a passing result.

Runtime deployment changes additionally require sequential service activation
and direct verification of service health, canonical capture, and derived-row
flow through the real deployed interfaces.

<!-- PROJECT-CONFIG-END v1 -->
