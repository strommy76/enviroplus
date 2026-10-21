# PROJECT-CONFIG.md — Enviroplus

This file contains only repository-specific authority. Portable agent doctrine is
loaded from the canonical `agent-config` materialization and takes precedence if
this file ever conflicts with it.

## Repository Responsibility

Enviroplus owns local environmental sensor display and collection, external
weather and air-quality collection, raw retention of local reads and provider responses, the
derived SQLite store (`readings` and the provider tables), and their backup lane.

## Authority and Persistence

- Provider response artifacts written through `shared.raw_retention` are the
  canonical source for replayable external observations.
- Tier 1 (canonical) is `shared.raw_retention`; every SQLite table is Tier 2 (derived):
  - Local sensor reads are canonical in `shared.raw_retention` as provider
    `local_sensors`: `enviro_dash3.py` retains every loop's reads there first,
    as each driver returned them.
  - `readings` is derived from them by `local_sensors.derive_row`; live and
    `local_sensors.py --replay DAY...` use that one projection, so rows rebuild
    from retention. Rows written before 2026-10-21 have no retained reads:
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
  document. That selected document owns runtime-tunable sensor calibration,
  thresholds, display behavior, and intervals. Repository content does not
  declare which profile is active on a host.
- Uncommitted `.env` owns secrets and host-specific infrastructure bindings.
- `config/backup.json` owns the database/raw-capture replication contract;
  `scripts/backup_enviro.py` is its supported execution path.
- Tests must isolate the raw-retention root and must never write to the live
  canonical capture tree.

## Service Boundaries

- `enviro_dash3.py` owns the local sensors, their display, and the canonical
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
- Repo-managed service files describe the intended service content. Which
  hardware-specific dashboard unit is active is host residue and must be proven
  from the running service manager, not inferred from this repository.
- Backup capture and off-host replication use the shared replication service;
  provider collectors and the dashboard do not implement competing backup paths.

## Supported Validation

Run from the repository root using the interpreter selected by the deployed
service or a developer environment satisfying `requirements.txt`, with the
sibling `shared` package available:

```bash
PYTHONPATH=.. python -m pytest
python -m ruff check .
python -m ruff format --check .
```

If Ruff is unavailable, that validation lane is red until the declared developer
environment is restored; absence is not a passing result.

Runtime deployment changes additionally require sequential service activation
and direct verification of service health, canonical capture, and derived-row
flow through the real deployed interfaces.

<!-- PROJECT-CONFIG-END v1 -->
