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
Pending implementation and observed checks; no success claimed here.
