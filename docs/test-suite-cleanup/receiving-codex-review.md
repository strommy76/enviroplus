04:06:52 AM EST · receiving reviewer

**Verdict: block merge pending one small fixture correction.** Reviewed `6b80e6b` against `8eea566`; no production regression found.

**F1 — CONFIRMED, low: the CO₂ comparison recreates an unreachable state.**  
[tests/test_screens.py:160](/home/pistrommy/projects/.tmp/enviroplus-test-cleanup-20261101/worktree/tests/test_screens.py:160) overrides the repaired helper with four CO₂-history entries beside four PM/gas entries. Four completed loops permit at most three closed intervals. It also sets CO₂ to `None` while retaining humidity `45.0`; the producer clears both through `scd41_shown`.

I executed the unchanged producer-loop AST with controlled inputs: history lengths progress through `(1,1,0)` to `(4,4,3)`, with absent CO₂ and humidity both `None`. See [enviro_dash3.py:440](/home/pistrommy/projects/.tmp/enviroplus-test-cleanup-20261101/worktree/enviro_dash3.py:440).

**Minimum correction:** use three absent CO₂-history entries, clear SCD41 humidity, and compare the CO₂ page specifically so humidity cannot satisfy the image-difference assertion. That reachable construction changes the actual CO₂ rendering. No framework or additional scenario is needed.

| Review question | Finding and evidence |
|---|---|
| Approved scope | **CONFIRMED:** exact 14 REMOVE + 10 MERGE; 179→155 functions; surviving parameter decorators unchanged. Only tests and provenance documents changed. |
| Lost required assertions | **REFUTED:** dry-run protections, Ambient absence/diagnostics, AirNow classification/error logging, dropout predicates and scrub lineage survive their merges. Anchors: `tests/test_backup_lifecycle.py:233`, `tests/test_collectors.py:69`, `tests/test_provider_collector.py:120`, `tests/test_raw_retention.py:148`. |
| Backup isolation | **CONFIRMED:** both replication functions are replaced before each failure override at `tests/test_backup_lifecycle.py:156`, `:182`, `:275`. The retained integration uses its explicit scratch-local alias at `:348`. |
| PMS validity | **CONFIRMED:** the pinned driver’s actual `read()` accepted the repaired 28-byte fixture, checksum **373**, returning PM values **1/2/3**. `tests/test_dash_loop.py:57`. |
| Revised oracle detection | **CONFIRMED, bounded:** inspected all ten before/fault/restored log sets and literal patches. Target source/test files remain byte-identical from witness revision `4da7879` to this head. `docs/test-suite-cleanup/fault-results.jsonl:1`. |
| Broader detection strength | **UNCONFIRMED:** those witnesses establish their specific violations, not universal mutation strength or physical/cloud behavior. |
| Over-building | **REFUTED:** existing helpers and APIs suffice; the archived fault method is inert provenance. `docs/test-suite-cleanup/fault-witness-method.txt:1`. |

Independent checks: **249 passed in 4.77s; Ruff check and format passed; worktree remains clean.**

| Axiom / admission test | Result and location |
|---|---|
| 1 · Truth is absolute | **VIOLATES:** F1’s substitute state contradicts its producer; `tests/test_screens.py:160`. |
| 2 · Cognition is adaptive | **CONFORMS:** AST comparison verifies reductions and unchanged decorators; `docs/test-suite-cleanup.md:34`. |
| 3 · Antifragility is doctrine | **CONFORMS:** provider/sensor variation retained; actual rollover exercised at `tests/test_raw_retention.py:262`. |
| 4 · KISS — simplicity is mandatory | **CONFORMS:** existing helper reuse; `tests/test_backup_lifecycle.py:156`. |
| 5 · Boundaries are determinate; interiors are free | **CONFORMS:** sibling transport stubs and temporary retention root; `tests/test_backup_lifecycle.py:98`, `tests/conftest.py:26`. |
| 6 · Maintenance is directional | **VIOLATES:** a helper consumer reintroduces the corrected inconsistency; `tests/test_screens.py:160`. |
| Preamble admission test | **CONFORMS:** bounded cleanup and required evidence; `docs/test-suite-cleanup.md:40`. |

**Remaining class:** reachable SCD41 state in the existing CO₂ comparison case. Fold F1 into this increment; Bryan’s explicit merge approval remains required.