**receiving reviewer — enviroplus test-suite audit, closing artifact 3a7ab2a (branch analysis/enviroplus-test-suite-audit-20261101), baseline 8eea566, shared 5cafbba.**
Seat clock not readable in this environment; no time is fabricated. Read the whole artifact: PROJECT-CONFIG, source, all tests, both author-family reviews, adjudication, cases.csv. No suite run, no rclone, no .env read — per dispatch.

**Verdict first: the audit is sound for operator adjudication. I would not block.** Every material finding verifies from the content; the classifications I sampled are correct; the two prior review errors were properly adjudicated. Two small items nobody named, below — neither changes a recommendation.

---

## 1. Material findings — verified

| # | Claim | Status | My construction |
|---|---|---|---|
| 1 | 3 backup tests leave real `replicate_tree` reachable through ambient rclone config | **CONFIRMED** | `tests/test_backup_lifecycle.py` — `test_failed_upload_keeps_its_snapshot`, `test_repeated_failures_do_not_accumulate_snapshots`, `test_retention_larger_than_the_backlog_deletes_nothing` stub only `replicate_file` (each `monkeypatch.setattr(..., "replicate_file", boom)`); `lane` fixture sets remote `test:` with no `rclone_config_path` → `backup_enviro.run` gets `None` → `_rclone` omits `--config` → `probe_remote_tree` runs `subprocess.run(["rclone","lsjson",...])` against ambient config. `run`'s `except Exception` continues the loop after the first source fails, so the tree source is really attempted. Both outcomes (transfer or config error) yield `run()==1`, so the pass hides the escape either way. |
| 1a | …severity: could a run have touched real remote backups? | **UNCONFIRMED, and bounded below** | method.md records current `rclone listremotes` = only `stocks_gdrive:`, no `test:`, no `RCLONE_CONFIG_*` env — so in the recorded 273-pass run `test:` almost certainly failed to resolve and no transfer occurred. That observation is author-reported; I could not re-verify it read-only without touching rclone, so prior contact stays UNCONFIRMED. **Nobody named this bound:** even in the worst case (a `test:` remote existing and pointing at gdrive), the tests write `test:backups/x/...` — a namespace that cannot overlap the live `stocks_gdrive:backups/enviropi` objects. The real harm class is uncontrolled subprocess/network egress under ambient credentials, not corruption of existing offsite backups. This calibrates the severity at *real isolation defect, no evidence of contact, low blast radius*. The audit's response (isolation assurance withdrawn, bare reruns stopped, REVISE with tree-stub) is proportionate. |
| 2 | PMS fixture checksum 0 vs required 373, 21 cases | **CONFIRMED** | I recomputed independently. The driver sums **bytes**, not words: `checksum = sum(0x42,0x4D)=143` + length bytes `0x00,0x1C=28` + `sum(raw_data[:-2])`. For `frame(1,2,3)`: words 0–12 = (1,2,3,11,12,13,300,90,20,4,1,0,0) → high bytes sum 1, low bytes sum 201 → 202. 143+28+202 = **373**. Stored word 13 = 0; driver raises `ChecksumMismatchError` before returning (installed 1.0.1 source in artifact). The audit's arithmetic is exact. Case scoping also verifies: 21 REVISE-marked dash_loop rows share the Run fixture; the 3 KEEP dash_loop cases (`replay_after_midnight`, `cutover`, `unreadable`) use `_retain_reads` and correctly escape the flag. Note: my own first pass summed words (628) — the byte-level sum is exactly the mistake a fixture author makes, which is itself evidence the fixture was written without executing the real driver path. |
| 3 | Circular replay count | **CONFIRMED** | `test_replay_reproduces_the_live_table_by_the_same_path` expected dict contains `"capture_days_scanned": summary["capture_days_scanned"]` — vacuous for that field; all other fields explicit. Minimal date-derived fix is correct and consistent with `test_replay_scans_one_capture_day_before_the_named_day`'s count of 2. |

## 2. Sample verification of REMOVE/MERGE — all correct

Checked every REMOVE by reading both sides:

- **Exact duplicates confirmed:** `test_repeat_within_the_same_day` ⊂ `test_consecutive_identical_payload` (same two calls, weaker asserts); `test_every_day_file_is_independently_replayable` asserts the identical 1,1,2 readback of `test_changed_payload_after_duplicate` (name claims multi-day; fixture is single-day); `test_fresh_root_starts_without_dedup_memory` is the line-for-line same two-root sequence as `test_dedup_state_does_not_leak_across_roots`; `test_an_unsafe_key_is_still_a_value_error` duplicates `test_unsafe_provider_key_is_refused[../evil]`; `test_unrelated_fields_are_ignored_not_projected` is a strict subset of the nominal full-row equality on the *same* PAYLOAD (which already carries `siteName`/`lookupBoundary`).
- **Import smokes confirmed callable-only**, and `shared.utils` has no consumer in the shown enviroplus source (the 2026-04-09 changelog mention is provenance only).
- **The Astra F3 correction landed:** the empty-Ambient case is now MERGE preserving `obs is None` — correct, because `ambient_wx.run` branches on `observation is not None` for the write decision and the destination matrix asserts only outcome. The final REMOVE=15 count recomputes correctly (14 original − empty-Ambient + unrelated-fields).
- **MERGE destinations preserve distinct assertions** in every case I read (4 dry-run cases, scrub lineage/byte tests, ERROR-log fold).
- Arithmetic: 153+53+15+9+43 = 273; module table sums to 273; REVISE breakdown recomputes (21 PMS + 3 backup-isolation + 12 screens + 5 other backup + 1 NWS + 1 provider replay + 3 raw_retention oracles = 43). All consistent.

**Adjudication concurrence:** GLM F2's missing-PK claim is correctly REFUTED — the `startswith` assertion literally contains `PRIMARY KEY`, so a PK-less SQL string cannot pass; KEEP_LIMITED with the format-coupling caveat is the right landing.

## 3. Proportionality — does it answer Bryan simply?

**Yes, with one presentation gap.** The honest answer to "are they all necessary?" is present and doctrinally correct: the 273 is 179 functions inflated by 94 parameterized extras; the real fat is ~24 functions (15 REMOVE + 9 MERGE); the 43 REVISE are case-level effects of **four** shared corrections (PMS checksum, render-state helper, backup tree stub, a few weak oracles) — not 43 problems. The report says this, but Bryan has to assemble the number himself. One sentence in report.md — "post-consolidation shape: ~155 functions, ~164 cases" or equivalent — would have closed the loop on the count he actually asked about. The audit's refusal to impose a count *target* is right; declining to state the *predicted result* is over-cautious.

**KEEP_LIMITED is not a hedge.** It changes no action (KEEP and KEEP_LIMITED both mean "keep") but carries real information: it prevents a later reader from over-claiming what a pass proves (e.g., the 7-shape Ambient matrix does not prove never-raises). Used consistently across ~50 rows. Cost is one extra column value; I'd keep it.

**Is 153 KEEP still too many?** On the evidence, no clear case for further purge: every KEEP row I sampled names a reachable input through a supported interface (operator contract edits, provider shape changes, ENOSPC, corrupt day files, cabled-lane dropouts, historical schema migration). Under Axiom 4/AGENTS r these are legitimate; "not observed in this house" is not phantom. Parameterized EPA edges and loader refusals are cheap, hand-derived, and distinct. The suite is large but its bloat is concentrated where the audit says it is.

## 4. Missed phantoms / nobody named

1. **Minor (nobody named):** `test_a_non_integer_failed_run_retention_fails_at_load` — 5 params exercise 3 distinct branches of the guard (`isinstance bool`, `not isinstance int`, `< 0`). "2", 2.5, and None all hit the same `not isinstance(int)` branch; the set collapses to 3 without losing a condition. KEEP is within judgment (cheap, distinct inputs); flagged only as a residual consolidation opportunity for the authorized implementation pass.
2. **Minor (nobody named):** `test_replay_scans_one_capture_day_before_the_named_day` is a count-only oracle of the same class the audit flagged elsewhere; its own CSV caveat already says so, but it holds a KEEP where the same shape earned REVISE elsewhere. One-line rubric note, not a defect.
3. I found **no misclassification** in my sample and no consequential phantom beyond the above.

## 5. Axiom check (reviewer pass on the artifact)

| Provision | Result | Location |
|---|---|---|
| 1 Truth | **CONFORMS** — counts, checksum arithmetic, inventory joins all re-verified; passes explicitly not promoted to detection strength | report.md AGENTS.r section; method.md |
| 2 Adaptive cognition | **CONFORMS** — inventory generated (pytest collection + AST), judgments are per-case proposals | method.md reproduction snippet |
| 3 Antifragility | **CONFORMS** — provider/sensor flux retained with deployment limits stated; no purge of rare-but-reachable cases | report.md "Preserve real boundaries" |
| 4 KISS | **CONFORMS** — no framework, no count quota, corrections are shared-fixture fixes, not 43 new mechanisms | report.md findings 5–8 |
| 5 Boundaries | **CONFORMS for the artifact** — the ambient-rclone escape is disclosed, assurance withdrawn, bare reruns stopped; the analysis does not claim isolation it doesn't have | plan.md, method.md addendum |
| 6 Maintenance | **CONFORMS** — every removal names its stronger destination; the one lost-assertion case (empty Ambient) was caught and corrected before closing | adjudication AstraF3 |
| Preamble | **CONFORMS** — finite per-case analysis + required reviews, proportioned to irreversible deletion decisions | plan.md |

## 6. Remaining class and next step

Remaining defect class in this artifact: **none found that changes a recommendation** — only the two minor notes above, closable in the authorized implementation pass or by one sentence each. Receiving review is complete.

**Simplest next step:** Bryan rules on the audit (merge/land the documentation). The audit is ready for that verdict as it stands. Test implementation — the ~24 REMOVE/MERGE edits, the PMS `frame()` checksum fix, the `replicate_tree` stub in the 3 lifecycle tests, and the weak-oracle renames — is one separate authorized, revertible branch, and is the prerequisite for safely rerunning the suite. No deletion should precede that authorization, exactly as the standing direction requires.

**Would block: no.**