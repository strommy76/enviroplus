# Enviroplus test-suite findings

**Most tests protect real boundaries; some are redundant.** Propose removing14
redundant functions and merging10 others while preserving their useful assertions.
Three shared fixture corrections account for36 of the45 REVISE cases; the other9
need individual oracle/name corrections. Fix these before pruning.

If all14 removals and10 merges are absorbed into existing retained functions, with
no parameter cases discarded or added, the predicted shape is **155 functions /
249 cases**, from179/273. This is a conditional result of the listed edits, not a
count target: all24 reduction candidates currently have one case apiece.

Baseline8eea566 has179 test functions and273 collected cases in13
modules. Parameterization accounts for94 extra cases. Count does not establish
necessity. [cases.csv](cases.csv) dispositions every observed node ID with original
test line, real code boundary, reachable input and evidence limit. No production
code or tests changed.

|Recommendation|Cases|Meaning|
|---|---:|---|
|KEEP|153|Live input/boundary identified; fault detection not claimed from a pass|
|KEEP_LIMITED|51|Boundary identified; assertions or deployment evidence are narrower than a broad reading|
|REMOVE|14|Redundant smoke or assertion subsumed by named stronger cases|
|MERGE|10|Combine setup while preserving distinct behavioral assertions|
|REVISE|45|Name, oracle or fixture does not establish the claimed property|

The14 removal candidates are content judgments, not experimentally observed proof
that all future faults remain detected after deletion. No deletion was attempted.
The10 MERGE labels do not mean10 removable checks; preserve distinct assertions.
The45 REVISE labels include21 cases sharing one invalid PMS fixture,3 sharing
one backup isolation omission, and12 sharing one screen-state helper. The other9
are individual assertion/name corrections, not one fourth shared fix. No new
mechanisms are proposed.

## Confirmed content findings and proposed dispositions

1. **Redundant smoke/duplicates:** five shared callable imports, two callable-only
   collector imports and the Ambient full-response classifier overlap
   behavioral collector/config/SQLite cases. The unrelated-field subset of nominal row equality is also redundant.
   Remaining removal candidates duplicate
   same-day dedup, one-record visibility, single-day1,1,2 replay, two-root separation
   and unsafe retain-key checks. Each CSV row names its stronger destination. Do
   not remove shared runtime utilities or useful independent assertions.
2. **Weak oracles:** provider replay sets expected `capture_days_scanned` to that
   same returned value. Other counts/no-retention-change assertions remain useful;
   replace this circular field with a date-derived expectation. The primary-key SQL case remains KEEP_LIMITED: its prefix explicitly asserts
   PRIMARY KEY and the actual SQLite execution establishes the declared syntax.
   The proposed rewrite was unnecessary; no missing-PK pass is claimed. Two backup source-preservation tests compare names/sizes, not actual source bytes.
   Revise only these expectations; no backup/test framework is proposed.
3. **Additional weak assertions:** shutdown records requested sleep durations but
   checks only their count. A single full-poll sleep satisfies that count oracle;
   inspect durations against the actual shutdown boundary. The loader test's
   secret-absence check inspects unchanged fixture CONTRACT and observes no loader
   behavior: remove that assertion/name claim while keeping URL/config checks.
   These are test revisions, not new shutdown or credential-handling code.

   **Names exceed assertions:** the day-boundary dedup case never crosses midnight;
   independently-replayable-days repeats one day. Retained-day sorting has only
   one day. The200KiB case is a cache-restart example, not evidence of a measured
   maximum-payload bound. Frame inequality does not isolate page-marker behavior.
   Rename to actual narrow claims or supply realistic distinguishing fixtures in
   a later authorized implementation.
4. **Unreachable composite fixture:** the five `False` render-page cases supply
   NULL HAT gas/pressure alongside absent cabled sensors. Both production render
   call sites use the state constructed after mandatory successful HAT reads; a
   HAT exception ends the process and gas division cannot produce None. Replace
   this with the live mixed dropout (PMS/TMP119/SCD41/outdoor absent; HAT present).
   Even the nominal _state(True) includes NULL gas-history gaps, also unreachable
   from successful numeric gas reads. Correct the shared helper across all uses,
   preserving real cabled/outdoor gaps. This is source reachability analysis, not
   injected runtime evidence or a proposal for new HAT recovery behavior.
5. **Impossible successful PMS fixture:** the pinned installed PMS5003 driver
   validates checksum before returning. Existing frame(1,2,3) encodes0; the actual
   frame requires373. Its18 Run-using functions expand to21 cases. Recommend
   correcting only the shared synthetic frame checksum, retaining the tests and
   avoiding duplicate production validation. This is driver source plus arithmetic,
   not an induced driver rejection/test-fault result.
6. **Ambient outcome versus observation:** the empty-response test also asserts
   obs is None, while its proposed destination currently asserts only outcome.
   The malformed-response case additionally checks observation absence and a
   nonempty diagnostic. Merge those assertions as well; do not simply delete
   either case on the rationale that outcome-only expectations subsume them.
7. **Backup isolation:** three failure-path tests replace only replicate_file,
   leave replicate_tree real and supply remote test: without a local config.
   They can resolve ambient credentials/remotes and still pass on first-source
   failure. Retain their lifecycle assertions but stub the sibling tree service
   for the unit property. The existing dedicated local-alias integration remains.
   No real remote use in the prior test run is established. Stop bare suite reruns
   until this is fixed or the execution boundary is explicitly constrained.
8. **Consolidation:** combine four dry-run setups while retaining no staging, no
   snapshot, no manifest and unchanged source bytes. Fold body-secret removal and
   lineage into exact-byte scrub checks. Fold related malformed ERROR-log and
   dropout assertions into existing collector cases. Keep any distinct pure
   classification claim when merging; parsed-but-unprojectable is distinct from
   malformed JSON. No exact post-consolidation test target is imposed.

## Preserve real boundaries; state uncertainty

Provider errors, field changes, NULL versus omitted values, repeated responses,
late revisions, corrupt retained bytes, storage errors, station staleness and
sensor gaps reach current supported interfaces. They are not phantom merely
because every example has not appeared in this house. Observed Ambient outdoor
absence directly supports those dropout cases. Shape/type tests govern Tier2
projection; rejecting a projection is not permission to discard Tier1 returns.

The supported manual backup CLI can overlap a scheduled run; one systemd timer
unit cannot overlap itself. Year2999 is an ordering fixture, not an operational
date claim or comprehensive concurrency simulation. Source explicitly excludes
older overlapping snapshots. Only one SQLite source is currently configured;
a second configured SQLite source or relative-root cwd change has no confirmed
active deployment consumer. Their rows distinguish supported-contract reachability
from observed deployment use. No new backup source/concurrency/path machinery is
authorized or proposed.

**AGENTS.r:** detection strength at this revision is UNCONFIRMED wherever no real
implementation violation was observed to fail a test. This read-only audit injects
none. Static comparison can identify duplicate assertions/circular expectations,
but is not a mutation result. PR24's six historical faults were recorded at393c201;
no new all-suite mutation result is claimed at8eea566. Live==replay and constant
comparisons establish agreement, not independent projection accuracy or an adequate
timeout budget. Substitutions must match actual driver/HTTP/shared-service returns
for the property in question; image dimensions/differences are not physical LCD
acceptance. Bryan's separate November1 physical acceptance is recorded in PR24.

## Module inventory

|Module|Collected cases|
|---|---:|
|tests/test_backup_lifecycle.py|20|
|tests/test_collector_wiring.py|12|
|tests/test_collectors.py|21|
|tests/test_dash_loop.py|24|
|tests/test_imports.py|5|
|tests/test_nws_wx.py|6|
|tests/test_provider_collector.py|40|
|tests/test_provider_contract.py|47|
|tests/test_raw_retention.py|41|
|tests/test_raw_retention_root_key.py|3|
|tests/test_raw_retention_write_failure.py|7|
|tests/test_room_dashboard.py|1|
|tests/test_screens.py|46|

## Verification and axiom-check
Canonical invocation on this unmodified source:273 passed in5.62s; Ruff check and
format check pass (26 files already formatted). This records baseline execution only: the uncovered ambient-rclone path defeats
a claim of fully controlled test isolation, regardless of the passing result.
Fault-detection strength remains unconfirmed. No deployment occurs.

|Provision|Determinate question -> result and content location|
|---|---|
|1 Truth|Counts/passes promoted to necessity or fault detection? CONFORMS: collected IDs joined exactly to cases.csv; AGENTS.r section and case limits prohibit that inference.|
|2 Adaptive cognition|Curated test space stands as fact? CONFORMS: pytest/AST define actual inventory; authored CSV judgments are proposals, not a whitelist.|
|3 Antifragility|Real provider/sensor flux discarded? CONFORMS: CSV retains live errors/revisions/gaps and separates projection from canonical capture.|
|4 KISS|Runtime/testing framework or arbitrary count goal added? CONFORMS: documentation and targeted reduction proposals only; no code deletion or mutation campaign.|
|5 Boundaries|Isolation/analysis/deployment conflated? CONFORMS for this corrected analysis: ambient-rclone and impossible fixture findings are explicit; prior full-isolation assurance is withdrawn. Actual suite boundary is VIOLATED pending later fixture correction; no safe rerun/deployment claimed.|
|6 Maintenance|Consumer/retained replacement assertion missing? CONFORMS: each case identifies real owner; proposed consolidation preserves distinct assertions.|
|Preamble|Work exceeds requested outcome? CONFORMS: finite per-case audit and mandatory cross-family review; no new service or speculative guard.|

Confirmed test-content findings are folded into requested recommendations for
operator adjudication. No product repair or operator-accepted residual is invented. The current audit
records required fixture corrections rather than pretending they are already fixed.
One whole author review artifact accompanies this audit; then PiClaude's two-family
receiving. Only Bryan decides landing and any later test implementation.
