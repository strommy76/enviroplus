19:30 EST · pi-claude-peer — final report of the Anthropic-family receiving seat (architecture-reviewer subagent); findings and section text verbatim, AGENTS row table condensed to its statuses and evidence lines. Scratch: /tmp/claude-1000/rv/{recompute.py,policy.py,mut.sh}

7:29 pm EST · receiving seat (Anthropic family) for pi-claude-peer · Stocks 12ee7da / Enviro a3fd046 against Shared 37b2aef

Verdict: ACCEPT. I would not block. I found 2 minor confirmed findings. Neither changes runtime sizing.

1 Contract seam: CONFORMS. Shared load_configuration + require_component_order/records/scheduled_deadlines + require_capture_policy ran on both configs at the tested commits, with Shared imported from the frozen tree (shared.__file__ asserted under receiving-shared-37b2…/pkg). All 7 components passed. The 4 captured ones (stocks_main, acq, tier1, enviro database) carry exact int rationals, int evidence and a derivation. The 3 direct ones carry int native_metadata_bytes_per_file and measure through shared.backup_estimates, whose measure_tree emits source_files. No component has estimate_argv. The frozen tree is byte-identical to the backup-shared-37b2aef tree the Stocks gate used (diff -rq empty). After capture, payload_estimate takes the native_overhead_fraction branch for every captured component, so none is silently mis-sized.

2 Values: CONFORMS, exact. Recomputed from captured-component-calibration-results.json (manifest sha256 prefixes match: 6a4f9829/baa616fe/c84d4f62):
- cold = max artifact/allocation: equal to config for all 4 (e.g. Enviro 26477/27595, main 17385691663/151902018919).
- margin = max |consecutive relative change| of whole-payload/source: equal to config for all 4. It is a maximum, not the mean, and each component uses its own value; the old shared tier1 margin is gone.
- Sample counts 5/4/4/5 match the derivation text.
- Evidence bytes: whole payload − artifact = 345/351/349/379 in every sample. Serializing the current Stocks capture format through Shared write_record also gives 345/351/349 in every sample.
- Every value is marked PROVISIONAL and names its settling measurement.

3 Producers: CONFORMS. Stocks measure returns {source_bytes = pg_database_size(current_database()), derivation}. Enviro returns {page_count×page_size, derivation}. The calibration script takes its denominator from delivery.result.staging_estimate.source_bytes, which the removed estimators produced with the same two queries, so the fit and the live measure share a denominator. Shared's command_measurement enforces nonnegative int bytes.

4 Removal: CONFORMS in code; one doc residue (F1). git grep at both heads finds no estimate_argv, database_bytes, staging_estimate, dump_ratio_margin, fractional_tree_estimate or estimate CLI mode outside reviews/evidence. Capture drops only the extra size query and the database_bytes field. verify compares facts only, so restore is unchanged. Enviro capture/verify bodies are unchanged.

5 Tests (AGENTS r). Each mutation was applied to the real producer in scratch copies:
| Mutation | Result |
| Stocks: extra key / wrong component binding / str bytes / empty derivation | KILLED |
| Stocks: SQL changed to pg_relation_size | SURVIVES the non-DB test |
| Enviro: page_size dropped / source_files added | KILLED |
| Enviro: freelist pages excluded | SURVIVES (F2) |
| Enviro: file st_size used instead of page product | SURVIVES (F2) |
- The Stocks SQL mutant is covered only by integration_db measurement == native pg_database_size. The gate log records that test PASSED (lines 1919-1920); I did not run it (no test DB) → UNCONFIRMED by me.
- Unmutated runs on the tested copies: Stocks measurement 3/3 passed with --noconftest. Enviro test_sqlite_backup 5/5 passed, including the native Shared run() integration with the local duplicacy binary in tmp.

6 Tested→head: CONFORMS. git diff --name-only 678b32d..12ee7da and 70cfbce..a3fd046 show only docs/ paths.

AGENTS rows: Preamble, 1-6, A, C, F, H, a, c, e-l, n, q CONFORM. B, D, E, G, b, d, m, o NOT EXERCISED. p VIOLATES (minor, F1). r VIOLATES (minor, F2).
- Preamble: net code removed (−77/−218 Stocks); no new mechanism.
- 1: one estimator, in Shared; producers emit native facts only.
- 2: no hand-maintained enumeration; components read from config.
- 3: latest own capture supersedes the cold seed.
- 4: project calculators deleted.
- 5: policy refuses before any side effects; producer errors exit nonzero.
- 6: fixtures and startup contract regenerated with the change.
- C: Enviro backup-contract.md ~l.620 and Stocks resilience l.6419 declare lifetime/silent/revert.
- F: configs hold .env paths/keys only; no values read.
- g: all 4 coefficients are exact maxima; PROVISIONAL with settling.
- h: Shared capture_estimate/measure_tree invoked, not duplicated.
- n: old Shared + new config → KeyError estimate_argv, a loud failure.

Findings:
| p | stocks docs/architecture/backup-lane-multi-database-design.md:6 | CONFIRMED (content) | Current-tense doc still says postgres_capture "owns … size estimates", so it presents superseded ownership as current | Replace with "source measurement"; Shared owns sizing |
| r | enviro tests/test_sqlite_backup.py test_capture_follows_only_the_collectors_sqlite_binding | CONFIRMED (executed: 2 surviving mutants) | The oracle == st_size on a checkpointed DB with no freelist cannot tell page_count×page_size apart from st_size or freelist exclusion. A refactor to either would leave the measure on a different denominator from the cold fit (~4% under on the cold run) and the test would still pass | Create freelist pages (delete rows, no vacuum) before measuring, and assert against the native PRAGMA page_count×page_size |

Observations, not findings:
- The "pin 37b2aef" is declarative only (PROJECT-CONFIG/README; Shared comes in through sibling PYTHONPATH). A mismatched Shared fails loud, so nothing is silent.
- The cold path applies the whole-payload margin to the artifact ratio, as directed. For acquisition the artifact variation exceeds it by 4e-7 relative, which is immaterial.

Input limits: integration_db, the full canonical suites and ruff were not run. Lexx #1099 and Shared #10 were not reviewed. The calibration inputs were taken from the delivery records as given, not re-derived from the production observations directory.
