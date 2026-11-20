## Verdicts

- **stocks#346 @ e25a2f6: ACCEPT WITH CHANGES** — the isolation direction is genuinely implemented (per-lane/per-store/per-timer failure containment, Wants-not-Requires decoupling, removed fallbacks), but the holdout policy correction the plan's final round claims as closed at adbf401 is **absent from the landing bytes**; land only after finding 1 is closed.
- **enviroplus#31 @ 99e6a5e: ACCEPT** — isolation refactor, fd ownership, provider-health lanes and empirically derived bounds all conform to direction and plan; two low-severity rows below are for adjudication, not blockers.

## Findings

| repo file:line | CONFIRMED/UNCONFIRMED | failure scenario | minimum correction |
|---|---|---|---|
| stocks src/backtest/walk_forward.py:246-251 | CONFIRMED | `{"enabled": null}` → `bool(None)=False`: holdout silently disabled, tuning unrestricted, no error. `{"enabled": true, "holdout_start_date": "NaT"}` passes the truthy check, parses to NaT, and NaT comparisons never block any window — a malformed policy reads as success (n, Axiom 5). Contradicts the plan's "Same-round final policy semantics" / "closed at adbf401", which claims observed null/NaT rejection; the delta's test_holdout_policy.py also omits both counterexamples, so the closure claim is false for these bytes (E) | reject non-boolean `enabled` and require a non-NaT parsed cutoff when enabled; add the null and NaT counterexample tests |
| stocks src/services/ops/systemd_unit_reconciler.py:467 | CONFIRMED (low) | `path.parent == root` filter guards writes to subdirectories, but `derived_unit_sources` returns only root-level paths from both generators — a guard for a case that cannot occur (KISS/Axiom 4) | remove the filter |
| enviroplus tests/test_sensor_io.py:9 | UNCONFIRMED | repeated TMP117 init failure: each attempt constructs a fresh `ExtendedI2C` (opens the bus); plan asserts "TMP's bus already finalizes" by analysis, and the fd-bounded test parametrization omits the tmp119 lane, so the no-leak claim rests on unexecuted analysis (p: conclusion by analysis, but I could not establish it) | add `tmp119` to the fd-bounded parametrization, or show the finalizer closes the fd |
| enviroplus config/unit_templates/enviro_provider_health.service.in:8 | CONFIRMED (low) | new template hardcodes the pimoroni interpreter absolute path, extending a value already duplicated across unit templates with no single source (direction 06:47); plan adjudicated the PYTHONPATH seam but not the interpreter path | accept as residual matching the established sibling pattern, or hoist the interpreter path to one derivation |

Not re-reported: the freshness `capture_failed` exclusion (freshness.py:249) and the FNSPID `return 0` on owned upstream failure are disclosed, dispositioned attributions in the plan; the failure remains in the payload and the owning unit's OnFailure path, so they do not silently vanish.

## Axiom check

| Axiom | stocks#346 | enviroplus#31 |
|---|---|---|
| 1 Truth/SSOT | CONFORMS — config/service_execution.json is the single source; tracked units derived via systemd_unit_sources.py:31-39 | CONFORMS — provider_health.json owns lanes with stated derivations; backup config single-valued |
| 2 Adaptive cognition | CONFORMS — no curated rosters; `(None,"capture_failed")` (freshness.py:249) is a two-value attribution policy, not a fact whitelist | CONFORMS — outdoor presence derived from ambient_wx `_OUTDOOR_KEYS` owner (ambient_wx.py:151), no copied roster |
| 3 Antifragility | CONFORMS — acquisition_health.py:56-66, freshness.py:118-133, systemd_unit_audit.py:1003-1016 contain per-item failures; Wants-not-Requires decouples jobs | CONFORMS — sensor_io per-lane `_observe`, provider_health.py:20-52 per-lane try, display/proximity failures non-fatal |
| 4 KISS | VIOLATES (minor) — reconciler.py:467 dead guard (finding 2); retained mechanisms otherwise trace to issue#345/F10 failures | CONFORMS — mechanisms trace to measured fd leaks (E1) and the corrected fit (E2); no retry service or re-setup engine added |
| 5 Boundaries | VIOLATES — walk_forward.py:246-251: malformed authoritative policy silently reads as permissive success (finding 1) | CONFORMS — provider_health exits 1 on any lane problem; per-lane detail retained; read-only DB open |
| 6 Directional maintenance | CONFORMS — Requires/fallback/multi-ExecStart superseded code removed with consumers updated | CONFORMS — eager init, ExecStartPre readiness gate, source_path removed from all live surfaces |
| Preamble admission | CONFORMS — added mechanism is only the required-policy check (which is itself under-implemented, finding 1); guards removed | CONFORMS — each mechanism names its observed failure; bounds provisional with settling measurements named |

## Limits of my input

- Read-only review: I could not execute tests, controls, or the fd baselines; all claimed violation demonstrations (5→205 fd growth, counterexample failures at prior revisions) are taken as artifact claims and remain UNCONFIRMED from this seat (l).
- The shared backup common source (draft SharedPR8) and the prior Astra/GLM/Opus reports were not supplied; backup-cleanup hunks were reviewed only for interaction (none found beyond plan-consistent value removal).
- Docs excluded from the deltas; systemd behavior, hardware, timer and alert receipt effects are NOT EXERCISED here — source review only, per d.
- Main baselines (8c3f423, 0350abe) and referenced files (failure-boundaries.md, observation JSONs, provider-health-intervals.*) taken as described, not inspected.