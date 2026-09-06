# PROJECT-CONFIG.md — Enviroplus

This file contains only repository-specific authority. Portable agent doctrine is
loaded from the canonical `agent-config` materialization and takes precedence if
this file ever conflicts with it.

## Repository Responsibility

Enviroplus owns local environmental sensor display and collection, external
weather and air-quality collection, provider-response retention, the derived
SQLite projection, and their backup lane.

## Authority and Persistence

- Provider response artifacts written through `shared.raw_retention` are the
  canonical source for replayable external observations.
- The SQLite database is the derived structured projection used by the display
  and Grafana. It must remain rebuildable from admitted canonical inputs where
  those inputs exist.
- Uncommitted `CONFIG_PATH` selects exactly one dashboard configuration
  document. That selected document owns runtime-tunable sensor calibration,
  thresholds, display behavior, and intervals. The current tracked profiles are
  `dynamic_config.json` and `dynamic_config.pi5.json`; repository content does
  not declare which profile is active on a host.
- Uncommitted `.env` owns secrets and host-specific infrastructure bindings.
- `config/backup.json` owns the database/raw-capture replication contract;
  `scripts/backup_enviro.py` is its supported execution path.
- Tests must isolate the raw-retention root and must never write to the live
  canonical capture tree.

## Service Boundaries

- `enviro_dash3.py` owns the local sensor display and its derived SQLite writes.
- `ambient_wx.py` and `nws_wx.py` independently own their provider collection
  loops and canonical response capture.
- `provider_collector.py` executes one committed capture contract from
  `contracts/` (`provider_contract.py` defines the contract boundary); the
  AirNow lane is `contracts/airnow_current.json`. A provider API change is a
  contract edit. The derived row is keyed by the provider's stated observation
  time and follows the provider's latest statement; every statement is retained.
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

## Review-data Egress

Repository-authored source, diffs, tests, and documentation may be dispatched to
the configured review seats. Live sensor/provider records, database contents,
credentials, secret-bearing configuration, and artifacts derived from them stay
inside their trust domain unless the operator explicitly authorizes that dispatch.

<!-- PROJECT-CONFIG-END v1 -->
