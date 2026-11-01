**Closing whole-artifact review · 3a7ab2ac · FINDER report for root adjudication**

Depth bounded to the named class: whether corrected classifications preserve each distinct asserted contract and accurately bound fixture/caller/transport reachability. Source/arithmetic only; nothing executed.

## Findings

**F1 — CONFIRMED (prior AstraF2, now closed by content).** `tests/test_dash_loop.py:61–67` `frame(1,2,3)` packs `>14H` with checksum word 0; supplied pinned `pms5003/__init__.py` `read()` sums SOF bytes (66+77=143), length bytes (0x00+0x1C=28), and `raw_data[:-2]` byte-wise (202 for this body) → required 373 ≠ stored 0; driver raises `ChecksumMismatchError` before returning. All 21 `Run`-using cases (tallied: 21, and the three dash KEEP rows — `replay_midnight`, `rewrites`, `unreadable` — genuinely do not use `Run`) carry the shared-fixture REVISE note in cases.csv. Unsupported "realistic driver returns" claim removed. Closed correctly; no production checksum layer proposed.

**F2 — CONFIRMED (AstraF1, closed).** `test_backup_lifecycle.py:72` lane config omits `rclone_config_path`; cases at :149, :165, :283 stub only `replicate_file`, so `run()` continues to the raw_capture source and `shared/offsite_replication.py:103–107` builds a `subprocess` argv without `--config` → ambient config resolution. cases.csv marks all three REVISE with the isolation defect and "Prior actual remote contact unconfirmed"; method.md "Review-discovered fixture boundary" discloses `rclone listremotes` observation (local config read, no network — within the audit's declared no-network boundary and disclosed); plan.md withdraws the isolation assurance and stops bare suite reruns; report.md's verification section no longer claims controlled isolation. Reachability bound is accurate.

**F3 — CONFIRMED (AstraF3, closed).** cases.csv `test_ambient_classifies_an_empty_response` → MERGE with "Preserve explicit obs is None together with empty outcome in the destination classification matrix"; verified: `test_collector_wiring.py:68–71` asserts `obs is None`; `test_collectors.py:54–70` matrix asserts `[1]` only; `ambient_wx.py` `run()` gates the write on `observation is not None` — a live consumer decision. Distinct contract preserved.

**F4 — CONFIRMED (AstraF4/GLMF2 dispositions, closed).** `test_unrelated_fields_are_ignored_not_projected` → REMOVE naming the stronger destination (`test_provider_contract.py:171` full-row equality over identical `PAYLOAD`, which already contains `siteName`/`lookupBoundary`); both use the same `project(contract, PAYLOAD)` input — strict subset, confirmed. NWS `test_load_settings_requires_configured_station_list` → REVISE (name exceeds the configured-order loading it tests), truthful-rename recommendation, no new guard.

**F5 — CONFIRMED (AstraF5, closed).** Shared `_state` gas-history NULL correction propagated to all uses including `[page-True]`, `pages_differ`, and `co2_reading` rows; reachability verified: production `gas_hist` appends `now[key]` post-`derive_row` division (numeric; HAT failure ends the process first), so a `None` gas-history entry is unreachable at both render call sites. Real PMS/SCD/outdoor gaps retained; no HAT recovery capability invented.

**F6 — CONFIRMED (totals).** Independently tallied every cases.csv row by module: KEEP 153, KEEP_LIMITED 53, REMOVE 15, MERGE 9, REVISE 43; sums 273; module subtotals match report.md's inventory (20/12/21/24/5/6/40/47/41/3/7/1/46). The REVISE breakdown sentence (21 PMS + 3 backup-isolation + screen helper cases) is illustrative, not claimed exhaustive; the remainder is covered by report items 2–3.

**F7 — CONFIRMED (PK refutation, correctly grounded).** method.md refutes "missing-PK would pass" from the explicit prefix `ts TEXT PRIMARY KEY` in the asserted SQL (a string without it cannot satisfy `startswith`) plus the nominal real-SQLite PK flag 1 — no mutation result claimed anywhere; cases.csv row is KEEP_LIMITED for serialization coupling only.

**UNCONFIRMED (statements about evidence, consistent with (l)):** prior actual remote contact in the historical run; current-revision fault-detection strength / mutation kill; physical LCD behavior. All are marked as such in the artifact; nothing rests on them.

**Attempted refutations — none succeeded.** I looked for: a REVISE/REMOVE row that still drops a distinct assertion (none found — every removal names a stronger destination I checked); a reachability claim exceeding the source (none); a count or pass promoted to necessity (none — AGENTS.r section and per-row limits prohibit it).

## Axiom check (analysis object)

| Provision | Determinate question → result | Location |
|---|---|---|
| 1 — Truth is absolute | Do corrected classifications and claims agree with the named source and its deterministic contracts? **CONFORMS.** PMS checksum arithmetic reproduced (373 vs 0); obs-is-None consumer fact preserved; PK refutation source-grounded; no mutation/detection inference drawn. | method.md §review-discovered; cases.csv dash_loop, collector_wiring, provider_contract rows |
| 2 — Adaptive cognition | Does a curated inventory stand as fact? **CONFORMS.** Every row joins generated collected IDs/AST lines; judgments are explicit proposals; recomputed totals match. | method.md reproduction snippet; cases.csv/collected-cases.txt identity |
| 3 — Antifragility | Are uncommon-but-reachable provider/sensor states discarded? **CONFORMS.** Flux cases retained with KEEP_LIMITED bounds; corrections target fixture fidelity, not coverage purge. | report.md §Preserve; KEEP_LIMITED rows |
| 4 — KISS | Is any mechanism added beyond the audit? **CONFORMS.** Documentation-only; corrections are recorded recommendations; no new test/backup/production framework; no count quota (15 REMOVE is a recomputed result, not a target). | report.md recommendation table |
| 5 — Boundaries determinate | Is isolation/realism accurately bounded so failure cannot read as success? **CONFORMS.** Ambient transport path disclosed and bounded; bare reruns stopped; impossible PMS success-frame and unreachable gas-history states named as fixture defects, not as observed behavior. | plan.md §boundary; method.md; report.md items 4–5, 7 |
| 6 — Maintenance directional | Do removals/merges preserve each distinct asserted consumer property? **CONFORMS.** Empty-Ambient obs-is-None, unrelated-field destination, dry-run assertion sets, and scrub lineage all explicitly preserved in destinations. | cases.csv MERGE rows; report.md items 1, 6, 8 |
| Preamble | Does the work exceed the operator-directed audit without a named failure? **CONFORMS.** Same finite artifact, corrected in place; required cross-family review; no scope growth into test or runtime repair. | plan.md; review-adjudication.md |

## Round closure under (o)

The named class — corrected classifications preserving distinct asserted contracts and accurately bounding fixture/caller/transport reachability — is fully dispositioned by the current artifact's content: every correction I could test against the supplied source holds, every prior confirmed finding is closed by content in the same read-only plan, and the unconfirmables are correctly labeled and load-bearing on nothing. **No remaining defect in the named class. No further review round is warranted by anything I found.** First-round reports are retained as immutable provenance only, correctly not presented as current recommendations. Actual test/runtime repair remains outside this authorization, awaiting PiClaude's receiving review and Bryan's landing verdict.

**Would block:** No. Close under (o).