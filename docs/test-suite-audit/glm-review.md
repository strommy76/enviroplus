# Independent review — Enviroplus read-only test-suite audit @ 296dbc1

Seat: FINDER (independent author-review). Object: audit artifact + baseline source as provided. All statuses per (l).

## Findings

### CONFIRMED

**F1 · Circular oracle in provider replay test** — `tests/test_provider_collector.py::test_replay_reproduces_the_live_table_by_the_same_path`: expected dict contains `"capture_days_scanned": summary["capture_days_scanned"]` — expected value read from the returned value; the assertion is vacuous for that field. All other summary fields are explicit. Audit's finding 2 is exact. Minimal correction: derive the expected count from the requested day and `today` (e.g. `["2026-09-05"], today="2026-09-05"` → 2, matching `test_replay_scans_one_capture_day_before_the_named_day`).

**F2 · PK test inspects serialization, not SQLite PK metadata** — `test_provider_contract.py::test_create_table_sql_declares_the_primary_key`: asserts `sql.startswith(...)` and reads PRAGMA table_info extracting only `r[1]` (column names); the pk flag (index 5) is never checked, so a table created without the PK would pass. Minimal correction: `assert next(r for r in db.execute("PRAGMA table_info(aq)") if r[1]=="ts")[5] > 0`, or a duplicate-key insert rejection.

**F3 · Backup source-preservation tests compare name→size only** — `test_backup_lifecycle.py::test_dry_run_leaves_the_source_tree_untouched` and `test_a_verified_run_leaves_the_source_tree_untouched`: both build `{relpath: st_size}` dicts; same-size byte replacement passes. Minimal correction: compare content digests. Audit correctly limits this to the two fixtures and does not propose a backup framework.

**F4 · Unreachable composite render fixture (5 cases)** — `test_screens.py::test_every_page_renders_full_and_absent_data[page-False]`: `_state(False)` supplies `gas` all-None and `pressure` None. In `enviro_dash3.py`, HAT gas/BME failures end the process before `state` is built (`read_sample` raises), and `pressure` comes from the mandatory BME read — the all-HAT-absent state is unreachable at both render call sites. Audit's finding 4 is source-derived and correctly labeled reachability analysis, not injected evidence. Minimal correction: mixed dropout (PMS/TMP119/SCD41/outdoor absent, HAT present), as proposed.

**F5 · Redundant smoke/duplicate set (15 REMOVE candidates)** — each verified against the named stronger case in the shown source:
- `test_repeat_within_the_same_day_is_a_duplicate` fully subsumed by `test_consecutive_identical_payload_is_recorded_not_restored` (same two retain calls, stronger record assertions).
- `test_every_day_file_is_independently_replayable` repeats the 1,1,2 readback of `test_changed_payload_after_duplicate_is_stored`; no multi-day fixture exists despite the name.
- `test_fresh_root_starts_without_dedup_memory` is the identical two-root sequence/readback of `test_dedup_state_does_not_leak_across_roots`.
- `test_an_unsafe_key_is_still_a_value_error` duplicates the parameterized `test_unsafe_provider_key_is_refused`.
- Five `test_imports.py` cases assert `callable(...)` only; each symbol is transitively imported/exercised by named behavioral tests; no `shared.utils` consumer exists in any shown enviroplus file.
- Two collector import-smoke and three Ambient classify cases duplicate `test_collectors` matrix rows (verified: full/empty/malformed shapes each present in the matrix).
Audit correctly labels these content judgments, not observed fault-detection proof.

**F6 · Names exceed assertions (4)** — verified: `test_dedup_does_not_span_the_day_boundary` only inspects `_LAST_SHA` key shape, never writes a next day; `test_days_lists_the_retained_days_oldest_first` has zero-then-one day, cannot establish ordering; `test_tail_window_exceeds_largest_measured_record` uses a synthetic 200 KiB payload, no measured bound asserted; `test_pages_differ_and_mark_the_current_page` asserts only frame inequality, no page-dot assertion. Also `test_load_settings_requires_configured_station_list` — see F8.

**F7 · Arithmetic and inventory consistency** — 178+59+15+8+13 = 273 ✓; module counts sum to 273 ✓; 179 functions + 94 parameterized extras = 273 ✓; the 13 REVISE includes the 5 absent-page cases ✓. The method.md reproduction snippet is a sound mechanical identity check (IDs ↔ CSV ↔ AST lines).

### UNCONFIRMED (statement about my evidence, not the claims — l)

**U1** — Canonical 273 passed / 5.62 s, Ruff pass, collection 0.42 s: recorded executions I did not rerun in this seat. Nothing in the audit rests on them beyond compatibility, which the dispatch itself states, so no adjudication depends on this gap.

**U2** — "PR24's six historical faults recorded at 393c201" and "Bryan's separate November1 physical acceptance": outside this artifact; referenced, not checkable here.

**U3** — `test_line_at_8eea566` values: the claimed AST verification is reproducible from the shown source, but I did not execute it; line numbers accepted as recorded.

**U4** — No-consumer claim for `shared.utils` is confirmed within the shown baseline; a consumer in files outside the artifact (if any exist) is not excluded by this review.

### REFUTED

None. I found no audit claim contradicted by the provided source. Spot-checked additional cases (`test_dedup_does_not_rescan_the_day_file` call-count trace: retain #1 tails once, None not cached, digest cached at end — `len(calls) == 1` holds; `test_success_does_not_remove_a_different_sources_snapshots` sort-below-ceiling fixture logic; `test_non_integer...[True]` bool-subclass rationale; `test_nws_replay_writes_fresh_newest_observation` freshness arithmetic) — all dispositions match the code.

### Nobody named (new finding)

**F8 · Disposition-rubric inconsistency (minor)** — `cases.csv` row `test_nws_wx.py::test_load_settings_requires_configured_station_list` is **KEEP**, yet its own evidence column admits "does not actually test missing-station refusal despite name." By the audit's own REVISE definition ("Name … does not establish the claimed property"), this row is the same shape as `test_pages_differ…` (REVISE). Cost of the inconsistency: a reader applying the rubric mechanically could treat name-only overstatement as either KEEP-with-caveat or REVISE, weakening the artifact's per-case authority. Minimal correction: either reclassify to REVISE (rename to what it tests — configured ordering/ages load), or add one sentence to report.md stating the applied boundary: KEEP_LIMITED/KEEP-with-caveat where a real reachable property is tested under a broad name; REVISE where the named property is not tested at all. Under that stated boundary, this row belongs in REVISE.

## Axiom check (source-derived, one row per current axiom + Preamble)

| Provision | Determinate question → result | Location |
|---|---|---|
| 1 Truth absolute | Are counts/passes promoted to necessity or detection? **CONFORMS** — collected IDs joined exactly to cases.csv; AGENTS.r section and KEEP/KEEP_LIMITED caveats prohibit the inference; pass explicitly labeled compatibility-only. U1 noted. | report.md "AGENTS.r"; method.md |
| 2 Adaptive cognition | Does a hand-curated inventory stand as coverage fact? **CONFORMS** — inventory generated (pytest collect-only + AST, reproduction script given); CSV judgments framed as proposals for adjudication, not a whitelist. | method.md; cases.csv header semantics |
| 3 Antifragility | Are provider/sensor flux cases dismissed as rare? **CONFORMS** — "Preserve real boundaries" section retains errors, revisions, gaps, staleness; shape tests scoped to Tier 2 with Tier 1 retention preserved. | report.md §Preserve |
| 4 KISS | Is a mechanism or count quota added? **CONFORMS** — read-only documentation; targeted reductions only; "No exact post-consolidation test target is imposed." | report.md §Consolidation |
| 5 Boundaries determinate | Is isolation/analysis/deployment conflated? **CONFORMS** — conftest autouse `ENVIRO_RAW_ROOT` isolation present in source; scratch declared; no deployed effect claimed; invocation errors disclosed, not bent assertions. | tests/conftest.py; method.md |
| 6 Maintenance directional | Are cases judged with owners/consumers traced? **CONFORMS** — every row names its live code boundary; consolidation preserves distinct assertions; F8 is the one rubric-boundary gap. | cases.csv `live_boundary` column |
| Preamble | Does scope exceed the operator's question with uncosted structure? **CONFORMS** — one finite per-case analysis answering "are they necessary and realistic"; two-family review cost declared against the silent-failure risk (wrong removal of needed protection) in plan.md. | plan.md §Direction |

## Remaining defect class under (o)

For the audit artifact itself: **per-case disposition-rubric consistency** (F8) — one instance found; a further round, if any, should expect only that class, which is closable by the one-sentence boundary statement or a single reclassification. For the test suite (outside this read-only outcome, folded for later authorized revision): vacuous/name-only oracles and the unreachable composite fixture are correctly identified but not yet repaired — repair awaits two-family review and Bryan's landing approval, exactly as the direction requires; no runtime/product repair is silently expanded into this audit.

**Would block:** No. The audit is sound for adjudication; F1–F4 confirm its headline content findings, F8 is a one-row/one-sentence correction the author can disposition without another seat round.