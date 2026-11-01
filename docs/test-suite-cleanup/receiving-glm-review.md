# Receiving review — enviroplus test-suite cleanup, head 6b80e6b vs base 8eea566

**Seat:** independent receiving reviewer (not pi-claude, not the author). Object received whole: complete delta, current tests/fixtures/implementation/config, operator direction (Oct 30 + Nov 1 03:32), plan, accepted audit 10fb169, both author reviews and adjudication, pinned PMS5003 1.0.1 source.

**Execution by this seat: none.** The rclone precondition was confirmed from content (below), so a suite run was permissible, but this seat did not execute anything; the 249-pass / Ruff / AST counts remain **author-reported** and are judged here only for internal consistency. Per E, content governs; per l, unconfirmed is a statement about my evidence.

**Verdict up front: I would not block on substance.** One confirmed low-severity finding — a residual of the exact class Astra named and the author claimed closed — should be folded (a one-literal change) or explicitly accepted by Bryan before his merge decision. No other defect class remains.

---

## Findings

### F1 — CONFIRMED (low): the co2-absence override still constructs the impossible history cardinality the fold exists to remove

`tests/test_screens.py:160` — `without["co2"], without["co2_hist"] = None, [None] * 4` inside `test_co2_presence_changes_rendered_content`, against the corrected helper (`tests/test_screens.py:94–99`).

In the real loop (`enviro_dash3.py`), `pm_hist` appends every completed loop; `co2_hist` appends only on an interval close, which cannot occur on the first loop. Therefore `len(co2_hist) ≤ len(pm_hist) − 1` at every render. The helper now correctly encodes this (4 PM / 4 gas / 3 CO2). But the override builds a state with the helper's 4-entry `pm_hist` alongside a 4-entry `co2_hist` — not producible by the producer, by the identical reasoning Astra applied to the gas length (astra-review.md F1) and the author adjudicated CONFIRMED and fixed. The fold corrected the generator; this direct construction two lines away survives it.

Impact: the asserted property (CO₂ presence changes rendered content) is unaffected — a 3-entry all-None history serves identically — so nothing currently passes or fails wrongly. The defect is fidelity only: one unreachable stand-in state in the class (r: substitutes only with behavior the real counterpart can produce) that this cleanup was directed to eliminate. Minimum fix: `[None] * 3` or `[None] * len(with_co2["co2_hist"])`. The author adjudication's "reachable chronology closed / no further author defect class remains" is incomplete by this one line.

### Everything else the dispatch asked — checked from content

**Scope exactness — CONFIRMED.** The delta touches only `tests/` and `docs/test-suite-cleanup*`; no production, shared, config, service, calibration, or data file changes. All 14 REMOVE, 10 MERGE, 3 shared fixture fixes, and the 9 individual oracle/name fixes from the approved audit are present, and I found no edit outside that enumeration. The dry-run source-byte REVISE was merged into the dry-run case exactly as its CSV row directs ("Combine with dry-run case using actual bytes").

**Removals redundant, merge assertions preserved — CONFIRMED.** Pairwise sweep of every deleted assertion: each is either verbatim in its destination (empty/malformed Ambient `observation is None` + truthy `detail` at `tests/test_collectors.py:69–75`; the three AirNow classifier shapes at `tests/test_provider_collector.py:120–122`; the ERROR-log assertion at :130–134; full/console-only dropout predicates at `tests/test_collector_wiring.py:74–79`; scrub secret-absence/lineage/digest-inequality at `tests/test_raw_retention.py:148–171`), strictly subsumed (nominal-row subset; same-day dup; flushed-record visibility; two-root separation; unsafe-key), or an approved removal (Ambient OK-case `detail is None`, ruled unprotected in the accepted adjudication). The dry-run merge loses nothing: snapshot, manifests, and staging all live under `staging` in this fixture, and byte comparison replaces the size-only oracle in both dry-run and verified paths.

**Rclone stub correct and complete — CONFIRMED.** `_stub_success` replaces both `replicate_file` and `replicate_tree` on the module, and all three failure-lifecycle tests (`tests/test_backup_lifecycle.py:156, 182, 275`) call it before overriding `replicate_file`. Every `run()` caller in the suite now has both transports stubbed, with one deliberate exception: `test_cli_records_both_sources_despite_first_source_failure`, the explicit local-alias integration the plan requires to stay real — and it supplies its own scratch `rclone.conf` passed via `--config`, so rclone never reads ambient credentials or remotes. No remaining path from the failure tests to real rclone.

**PMS fixture valid — CONFIRMED.** Re-derived independently against the pinned 1.0.1 driver: checksum = sum(SOF)=143 + length bytes(0,28)=28 + body byte sum=202 → **373**; the new `frame()` (`tests/test_dash_loop.py:58–65`) emits a 28-byte `raw_data` (13-word body + checksum word) whose stored word is exactly that value, and `local_sensors._pms_words` consumes the same 28-byte shape. The frame the fake driver returns is one the real driver would accept — the reachability requirement, without claiming a hardware transaction.

**Revised oracles actually detect (r) — CONFIRMED, bounded.** Each of the ten revised/merged oracles has a literal production patch whose observed failure is recorded in `fault-results.jsonl`, and I verified each patch targets real current source text (e.g. `_shift_day(wanted[0], -1)`, `record["sha256_as_received"] = original_digest`, the `elif kind == "tree":` block) and that each named test still exists verbatim at head. Caveat the doc itself states: the observations are at 4da7879; head-revision detection rests on the claim that only the screen helper changed since, which is consistent with the artifact but is argued, not observed. No broader mutation strength is claimed anywhere — correct under r.

**Over-built — no confirmed instance; one proportionality note for the operator.** The ten fault witnesses and the five provenance documents are the one element beyond the operator's literal enumeration (14/10/3/9). They are required by the plan's own method (r forbids detection claims without observed violations; H requires committing method/results/provenance; k requires the review artifacts), prominently disclosed, bounded, and the method file is inert `.txt`. I concur with GLM's closed-without-action on the absolute paths / non-idempotent `mkdir()` (host paths are already public throughout this repo; re-execution fails loud, which is correct for one-use provenance). Whether the witness campaign was the minimal way to satisfy r (versus making no detection claims at all) is a proportionality judgment that belongs to Bryan at merge, not to this seat.

**Counts — UNCONFIRMED by this seat, internally consistent.** Not executed here. Arithmetic checks out from content: 25 functions deleted, 1 added (179→155); 273−25+1=249 cases; 26−1 deleted file=25 formatted files. Nothing in the content contradicts the reported pass.

### Dispute / extension of prior reviews

GLM's "no remaining fixture defect" was already refuted by Astra F1; I extend that refutation — the same impossibility survives at `tests/test_screens.py:160`, which no prior artifact named. I otherwise concur with the closed findings in both author reviews after independent verification, and with the adjudication's dispositions.

---

## Axiom-check (object: head 6b80e6b)

| Provision | Question | Result |
|---|---|---|
| 1 Truth is absolute | Do stand-ins use only counterpart-producible behavior; are oracles independent? | **VIOLATES narrowly** at tests/test_screens.py:160 (F1). All other revised oracles are date/byte/driver-contract/declared-bound independent, with observed fault evidence bounded to 4da7879. |
| 2 Cognition is adaptive | Did a count quota or curated inventory drive deletion? | CONFORMS — every edit traces to an audited case; count stated as conditional outcome; all 94 parameterized extras retained. |
| 3 Antifragility | Was reachable variation discarded? | CONFORMS — dropout/NULL/omission/revision/rollover semantics preserved; day-boundary test strengthened with a real UTC rollover. |
| 4 KISS | Any mechanism without an observed/directed need? | CONFORMS — test code plus plan-required provenance; witness campaign bounded and disclosed (proportionality note above for the operator). |
| 5 Boundaries | Any path to ambient remote/live data or production change? | CONFORMS — sibling stubs precede all suite runs; only the intentional scratch-config local-alias rclone remains; no production/config/data bytes touched. |
| 6 Maintenance | Was the shared fix evaluated across its whole consumer surface? | VIOLATES narrowly by F1 — the helper was corrected, but one sibling direct construction in the same file escaped the fold. |
| Preamble | Extra work beyond the outcome? | CONFORMS with the noted witness-proportionality item, which the doc itself justifies against r's requirement; final call is the operator's at merge. |

---

## Verdict

**Not a block on substance.** The delta is the approved scope, executed with the assertions the audit required preserved; the isolation, PMS, and oracle repairs are correct. One confirmed low finding (F1) remains inside the class the author's last fold claimed closed: fold the one literal (`[None] * 4` → 3) or have Bryan accept it as residual, before his merge decision. After that fold, no further review round is warranted — no defect class remains that this review expects to find. Merge remains Bryan's explicit call either way; suite-pass counts stay author-reported unless someone executes at head.