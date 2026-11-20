6:54 PM EST · opus receiving seat (independent) — stocks#346 @e25a2f6, enviroplus#31 @99e6a5e

## Verdicts
| PR | Verdict | Block? |
|---|---|---|
| stocks#346 | **ACCEPT WITH CHANGES**: three small, non-blocking corrections (S-1, S-2, S-3); S-4 goes to the operator | No |
| enviroplus#31 | **ACCEPT WITH CHANGES**: one test-evidence gap (E-1); E-3 goes to the operator | No |

What I ran: the focused suites in scratch clones (`git clone --shared`, no source repo mutated, no DB/Postgres, `-m "not integration_db"`). Stocks: 11 touched modules, **195 passed** (.venv/bin/python, PYTHONPATH=~/projects). Enviro: test_dash_loop/provider_health/sensor_io/screens, **94 passed** (pimoroni venv). I left out test_sqlite_backup and test_env_completeness (the backup-adoption scope, and a real .env).

Mutations (each applied to the real implementation, then restored with `git checkout`):
| # | Mutation | Result |
|---|---|---|
| 1 | freshness.py per-lane `except Exception` narrowed to ZeroDivisionError | FAIL test_failed_timestamp_lane_preserves_healthy_sibling ✔ |
| 2 | acquisition_health per-store catch narrowed | FAIL test_unreadable_store_preserves_sibling ✔ |
| 3 | daily_history_coverage:69 drop `or "acquired_at" in item` | FAIL failed_stale/failed_future ✔ |
| 4 | freshness.py:249 restore `is not None` (remove the capture_failed attribution) | FAIL failed_no_timestamp ✔ |
| 5 | failed lane `problem="observation_failed"` → None | FAIL ✔ |
| 6 | fnspid `return 0` removed / audit timer catch narrowed | FAIL ✔ / FAIL ✔ |
| 7 | provider_health per-lane catch narrowed | FAIL 2 tests ✔ |
| 8 | sensor_io: SystemExit dropped from PMS tuple / gas bus close removed / SCD connection not reused / BME+LTR get a new SMBus per init / `"bme280" in sample` guard removed / proximity catch narrowed | FAIL every one ✔ (gas fd 6→406, SCD 5→205) |
| 9 | walk_forward `raw["enabled"]` → `raw.get("enabled", False)` (or `True`) | **SURVIVES**: 21/21 pass |
| 10 | reconciler:491 `if path.parent == root` → `if True` | **SURVIVES** |
| 11 | sensor_io:38-40 close-on-open-failure removed | **SURVIVES** |
| 12 | local_sensors:128 `last_with` → last-sample-only for BME | **SURVIVES** |
I also checked the plan's claim that TMP119's bus "already finalizes": 200 failed TMP119 inits leave fds flat at 4→4. CONFIRMED.

## Findings
| repo file:line | Status | Failure scenario | Minimum correction |
|---|---|---|---|
| S-1 stocks tests/test_holdout_policy.py:341-347 | CONFIRMED (mut. 9) | The test accepts `(KeyError, ValueError)`, but neither parameter omits `enabled`. Restoring a permissive default goes unnoticed (mutation 9 passes all 21 holdout tests). With `get("enabled", False)`, a policy file that loses its `enabled` key silently disables the holdout, so tuning contaminates the holdout. That is exactly the F10/GLM2 class. Runtime is correct today; only the evidence is missing. | Add the one parameter `{"holdout_start_date": "2026-01-01"}`, which expects KeyError. Or drop KeyError from the tuple so the test stops claiming coverage it doesn't have. |
| S-2 stocks src/services/ops/systemd_unit_reconciler.py:491 | CONFIRMED (mut. 10) | `derived_unit_sources` only ever returns `root / name` for top-level names, so the guard is always true. It is a guard for a case that cannot occur, and no test covers it. | Remove the `if`. |
| S-3 stocks scripts/admin/refresh_factor_attribution_cache.py:15,20 | CONFIRMED | The docstring still says the cache is "wired into stocks.service ExecStart". It now has its own unit, pulled by Wants. A superseded statement still presented as current (p). | Update the two lines. |
| S-4 stocks config/service_execution.json:23,30,45 | CONFIRMED (in-plan) | The new JSON config adds three copies of the `/home/pistrommy/projects/stocks/.venv/bin/python` and repo-root literals. In the same PR, backup.json removes exactly that literal ("bare python = service's own interpreter"). The render is an identity copy (each unit is its own template), so the policy adds a second tracked copy with no derivation. The plan ("configure changed directives/commands", "preserve paths") authorizes this. | Operator call under E against the 06:47/06:50 no-hardcoded-config direction. Cheapest option: drop `Service.ExecStart` from the policy and keep commands in the unit files, as every other stocks unit does. |
| S-5 stocks freshness.py:249 + daily_history_coverage.py:69 | CONFIRMED behavior; harm low | A fetch-time failure records `{start,end,error}` and no `acquired_at` (daily_history_capture.py:44,121). With S5, those items are exempt from both the coverage check and the age check. Constructed: an all-failed latest run reads `lane_problem=None` at +0, +30 and +365 days. The freshness backstop never ages them. The other owners still fire: capture's OnFailure each failed run, and tier1 `acquisition_completion_overdue`. Nobody disclosed the indefinite age exemption. | Accept as residual, or age untimestamped failures from the run's `completed_at`. Weighing is the adjudicator's call. |
| E-1 enviro sensor_io.py:38-40; local_sensors.py:128-133 | CONFIRMED (mut. 11, 12) | No test fails when the bus close-on-failed-open is removed. That path needs `_get_funcs` to fail after `os.open` succeeds, which is rare but reachable. Likewise, the `last_with` semantics for the five newly nullable lanes, which the plan directs, have no failing test. Rule r: they ship unevidenced. | Accept as plan-directed and unevidenced, or add one construction each. I would not delete either. |
| E-2 enviro sensor_io.py:135-136 | CONFIRMED code path; trigger UNCONFIRMED | The cleanup reaches private `gas.adc._ads1015._i2c`, which the plan discloses. If an upgrade of the ads1015 or enviroplus driver renames those attributes, the AttributeError raised inside the except escapes `_observe` (only OSError/RuntimeError/SystemExit are caught) and ends the whole capture on the next gas failure. Isolation then depends on the installed driver version. | Pin ads1015/enviroplus in requirements, or include AttributeError in that one cleanup. |
| E-3 enviro enviro_dash.service (ExecStartPre removed) + sensor_io `_observe` | CONFIRMED (plan-disclosed) | Before: a HAT sensor fault ended the process, and Restart/OnFailure paged. After: the failure is only a PARTIAL Tier-1 record and a journal warning. No health lane covers local readings. The PR creates for local sensors the same gap it closes for providers in E2 ("OnFailure alone cannot detect missing data"). | Operator call. Option: a `readings` lane in provider_health.json once the hardware is reconnected (it would read stale while the hardware is disabled). |
| E-4 enviro config/unit_templates/*.in vs root enviro_backup.service.in | CONFIRMED, minor | There are now two template locations for derived units (Axiom 6, cognitive load). | Optional: put the new templates next to the existing one. |

I checked these and found no defect: stocks.service Wants→fred/factor isolation (factor attribution does not read FRED data), per-symbol capture failure exits nonzero (daily_market_capture.py:155), fnspid upstream OnFailure present, ops alert is state-transition based (no 60 s re-page spam), screens render None, readings NULLs are accepted by the real schema, TMP119/PMS serial lifetime, audit fallback unit name (matches the existing reader at :1025).
Disputes with the prior receiving adjudication (12:44): none on S3-1/F10-1/E1-1/E2-1/F4-1 as folded. Nobody named S-1, S-2, S-3, S-5 (the age exemption), E-2 or E-3.

## Axiom check (AGENTS.md, read this turn)
| Axiom | Result | Location / construction |
|---|---|---|
| 1 Truth | CONFORMS | Failed lanes/stores carry `observation_failed`, `row_count=None` and the error detail. No value is invented. derive_row gives NULL; holdout refuses a missing file or cutoff (mut. 1,2,5) |
| 2 Adaptive cognition | CONFORMS | Lanes, units and directives are policy in config. No curated fact roster. Exception tuples are the installed drivers' documented types |
| 3 Antifragility | CONFORMS (source); native UNCONFIRMED | Mutations 1-8 show one lane/store/timer/sensor failing while siblings survive. E-2 is a driver-version dependency |
| 4 KISS | VIOLATES (minor) | reconciler.py:491 guards a case that cannot occur (mut. 10) |
| 5 Boundaries | CONFORMS, with ownership caveats | Exits are nonzero for failed lanes (mut. 4,6,7). S-5 and E-3 move alerting to other owners by design |
| 6 Directional maintenance | VIOLATES (minor) | refresh_factor_attribution_cache.py:15,20 still describes the superseded wiring; E-4 adds a second template location |
| Preamble admission | CONFORMS | New mechanisms each name an observed failure (fd leak, LTR crash, serial ExecStart). The service_execution renderer is admitted by the plan's minimum-parts reasoning (four .in files avoided); S-4 questions its ExecStart scope |

## Limits of my input
- I ran no canonical full suite, no integration_db lane, no Ruff, no native systemd/hardware/alert effect, and no Shared PR8 tuple (test_sqlite_backup skipped). Both PRs depend on shared code; I ran against the ~/projects/shared checkout.
- Issue texts #345/#30 and the 06:47/06:50 direction wording were not in the packet; I judged against the packet's recorded decision and the in-repo failure-boundaries.md plans.
- I did not exercise display/PMS GPIO-claim lifetime on repeated init failure, because that would claim real GPIO on this host.

Would block: **neither PR**.
