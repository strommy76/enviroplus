# Test boundary coverage cleanup

## Plan, authority and lifetime
Bryan approved implementing the bounded Enviroplus cleanup November1 at03:32EST,
relayed by PiClaude in broker e1beb15b-3e28-49d0-ad80-78ec30dfd4e3. The source
questions/direction are supplied verbatim to reviewers; this record states the
decision rather than inventing operator wording. Scope is the audit at10fb169:
14 redundant-function removals,10 assertion-preserving merges,3 shared fixture
corrections affecting36cases, and9 individual oracle/name fixes. One plan, one
branch and one PR; no production/config/service/calibration/data changes.

Permanent test code can silently permit future defects. Canonical checks, axiom-
check and spawned Astra plus GLM-5.3/Ollama whole-delta review are required before
PiClaude's separate two-family receiving. Bryan decides the eventual merge after
those results; implementation approval does not merge unseen code. Revert this
test/document increment to undo it. There is no runtime activation/deployed effect.

Baseline enviroplus8eea5664f196bc91b97dadf92e33af5643864f34; shared source
5cafbba3c19a7d52901083dcd0b8b26635e178be. First fix the three backup failure tests
to stub their sibling tree service before any suite run. Keep the explicit local
alias integration. Use the existing real pytest fixtures/temp-root isolation,
existing supported application/retention APIs and deployed Python environment.
All scratch/method/logs and this worktree stay beneath this one effort directory.
No .env or live data access. All tests act on effort-local fixtures.

## Approach and current-practice check
Reuse current supported pytest parameterization/monkeypatch and official fault-
detection method already checked during the same-day audit:
https://docs.pytest.org/en/stable/example/parametrize.html ,
https://docs.pytest.org/en/stable/how-to/monkeypatch.html ,
https://cosmic-ray.readthedocs.io/en/stable/index.html .
Use current pinned PMS5003 1.0.1 read() checksum contract to repair the existing
frame builder; no equivalent independent builder/validator is exposed by that
driver. Preserve cabled dropout/history variation while making mandatory HAT
state reachable. Merge useful assertions into existing cases rather than reducing
parameter cases or adding services. Count projection155functions/249cases is a
conditional outcome, not a target; preserve distinct contracts over that estimate.

Observe selected actual implementation faults fail improved/retained tests in
this isolated worktree, restoring original source bytes between them. Record
property, exact patch and targeted failure/baseline result. No production source
is edited; no broad mutation platform or all-suite mutation score is proposed.
A passing suite alone never certifies every property. Checks use the existing
canonical interpreter, lint/format and actual suite only after isolation repair.

## Construction axiom-check
|Provision|Question -> result, planned content|
|---|---|
|1 Truth is absolute|Do tests assert independent input/output contracts rather than circular outputs? CONFORMS: correct replay count, byte comparison, duration checks; remove unchanged-fixture secrecy assertion; actual fault evidence bounded by property.|
|2 Cognition is adaptive|Does a count quota/curated inventory drive deletion? CONFORMS: exact audited source/observed collection defines cases; no parameter variation discarded to meet a count.|
|3 Antifragility is doctrine|Are genuine gaps/provider variation lost? CONFORMS: preserve missing/NULL/revision semantics, correct shared PMS/HAT fixtures rather than adding production recovery paths.|
|4 KISS—simplicity is mandatory|Any unconsumed runtime code/framework? CONFORMS: tests only, existing helpers/APIs, no new canonical service or generic validator.|
|5 Boundaries are determinate; interiors are free|Can test execution reach ambient remote/live data? CONFORMS prospectively: repair sibling stub first; retain explicit scratch-local alias; tests' throwaway retention root remains enforced.|
|6 Maintenance is directional|Do removals lose consumer assertions? CONFORMS: audit10fb169 destinations plus preserved obs/diagnostic/lineage/no-write assertions; remove dead callable-only tests/helpers/imports with no consumer.|
|Preamble admission test|Extra work beyond outcome? CONFORMS: one finite cleanup, canonical gate and required reviews; selected fault witnesses satisfy r, no fleet campaign or new mechanism.|

## Validation and review
Implemented on this one branch. Functional changes began at4da7879; author review at e7ae9f6
then required only the two-literal screen-history fold recorded below. Latest
canonical249passed in4.61s after that fold (previously4.68s), Ruff
check and format pass (25files). AST finds155functions: actual consolidation is
179->155functions and273->249cases, with all94parameterized extras retained.
Runtime source, shared dependency, configuration and data are unchanged.

The3sibling tree stubs were fixed BEFORE the first suite invocation. Both failure
lifecycle and explicit local-alias integration paths ran in the actual suite; no
real ambient-configuration path remains in these failure tests. No external
remote/hardware/service action was used. A one-use edit worksheet initially
stopped on a docstring-only module, before any test run; partial patch was kept
locally and baseline test bytes restored before corrected application.

PMS frame(1,2,3) now produces28bytes/checksum373, matching the pinned driver's
byte-sum contract, not an observed hardware/serial transaction. Screen state keeps
mandatory HAT gas/pressure and numeric gas histories, while retaining reachable
PMS/SCD/outdoor gaps. History endpoints match the current corresponding reads.
Tests are renamed where the old name claimed more than the assertion.

Ten actual production-implementation faults were made ONLY in this isolated
worktree at4da7879, each after its targeted baseline passed; each was observed to
fail at an assertion, then exact original source restoration passed the same
targets. Complete literal patches/targets/outcomes are fault-results.jsonl and
the inert one-use method archive is fault-witness-method.txt in
[the evidence directory](test-suite-cleanup/). This is not an all-suite mutation
score or certification of unexercised properties.

|Observed implementation fault|Property whose assertion failed|
|---|---|
|Full-poll sleep instead of shutdown-check sleep|Requested sleep duration/total wait bound|
|Scan begins two preceding days rather than one|Independent three-capture-day expectation|
|Dedup cache omits day identity|Same payload retained/readable across actual UTC rollover|
|Retained filenames returned unsorted|Out-of-order scratch days must enumerate oldest first|
|Source first byte changed without size change|Both dry-run and verified-path source byte preservation|
|Staging created before dry-run branch|No staging/snapshot/manifest artifact on dry run|
|Empty response returns an observation object|Merged observation-absence assertion|
|Malformed response returns an observation object|Merged malformed observation-absence assertion|
|Malformed diagnostic suppressed|Merged nonempty diagnostic assertion|
|Stored digest labeled as received digest|Merged source-lineage assertion|

The same-size write is an induced violation in the real backup implementation,
not a claim that transport was tested or this corruption was observed in live
operation. Other driver/HTTP/replication stand-ins remain outside the property
they isolate and use possible counterpart returns. Optical LCD, physical accuracy,
real cloud transfer and every future test fault are not certified by these passes.

## Implementation axiom-check
|Provision|Result, location and executed construction|
|---|---|
|1 Truth is absolute|CONFORMS: exact source-fault outcomes at4da7879 are retained; actual count155/249; replay count and source bytes independent; no passing-suite necessity/accuracy claim.|
|2 Cognition is adaptive|CONFORMS: actual pytest/AST inventory, no artificial count quota or dropped parameter variants; per-case decisions follow audit10fb169 rather than curated executable registry.|
|3 Antifragility is doctrine|CONFORMS: actual UTC rollover and distinct missing/NULL/provider-state assertions retained; PMS/state helper repairs make permitted variation realistic without adding production recovery logic.|
|4 KISS—simplicity is mandatory|CONFORMS: tests only;24functions consolidated, empty sections/import smokes removed; no new service, test framework or canonical validator. One-use method kept inert as provenance.|
|5 Boundaries are determinate; interiors are free|CONFORMS: sibling tree stubs precede suite execution; explicit local-alias integration preserved; faults stay in isolated worktree, source restored byte-for-byte and final suite passes.|
|6 Maintenance is directional|CONFORMS: whole affected shared-fixture surface corrected; observed merged assertions fail on real faults, not just claimed preserved; source/config/service paths unmodified.|
|Preamble admission test|CONFORMS: exact approved cleanup plus bounded r witnesses/canonical and required reviews; no extra product capability or broad mutation campaign.|

Whole-delta author Astra/GLM reports and root dispositions are in
[test-suite-cleanup/review-adjudication.md](test-suite-cleanup/review-adjudication.md).
Astra's single confirmed fixture-chronology finding is corrected: four PM/gas
loop entries coexist with three closed CO2 intervals. Both presence branches
were constructed from the actual helper and verified4/4/3 with numeric HAT and
matching PM/gas endpoints. Current CO2 need not equal the last closed interval.
No further author defect class remains; next is PiClaude's separate two-family
receiving on the final whole artifact, then Bryan's eventual merge decision.
No landing or deployment of this cleanup is claimed.

One post-review canonical command was mistakenly launched from the parent
projects directory: it failed at collection with26 errors and ran no tests.
Corrected worktree invocation passed249in4.61s; no application/assertion changes
were made for this invocation error. Failed collection output stays private
in the effort. The fault witnesses are reported at4da7879 only; their targeted
source/test functions are unchanged by the screen-helper-only fold. No broader
current-revision mutation strength is claimed.
