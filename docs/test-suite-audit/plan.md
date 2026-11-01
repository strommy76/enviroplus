# Enviroplus test-suite audit

## Direction, boundary and lifetime
Bryan asked on October30 at19:52 whether the273 tests are necessary and cover
realistic cases, then queued a test-suite audit on November1. Source: PiClaude
broker0cf91d4b-4275-47ec-8cac-c2110ee23e6d (November1 00:00EDT), preserving
the original direction for the executors. Only the newly named read-only audit
is this plan; calibration/LCD/worktree cleanup are separate efforts.

Read-only analysis at enviroplus8eea5664f196bc91b97dadf92e33af5643864f34 and
shared5cafbba3c19a7d52901083dcd0b8b26635e178be. Every collected test case must
join a source-based finding about a live input/reachable failure, duplicate or
implementation-mirroring assertion. Different parameters count as separate cases,
not separate authored test functions. Recommend retention/removal/merging only
from that content. Trace ownership through current production code/contracts;
no arbitrary target count and no inference that rare means unreachable.

One effort/branch/PR contains inventory, evidence, recommendations, this C/H
declaration, review and source provenance. No tests or production code/config/data
are changed, no fault is injected and no network/hardware/service operation is
performed. Canonical checks use existing test isolation and scratch beneath this
effort. The audit is a durable decision artifact whose error could silently lead
to later removal of needed protection. Before handoff, spawned Astra and GLM-5.3
through Ollama review the whole artifact plus the unmodified implementation/tests
at a named revision; the author dispositions each finding. PiClaude then conducts
its separate two-family receiving. No test deletion or main landing before that
and Bryan's explicit merge verdict. Revert the audit documentation to undo it;
no deployed effect exists for this read-only increment.

## Approach checked against current practice
Read official pytest parameterization and monkeypatch documentation and Cosmic
Ray's mutation-testing definition on November1. Collect-only supplies actual case
IDs; AST/source inspection supplies function/line/calls and assertions. Mocked
network/disk/hardware behavior is acceptable only if the real counterpart can
produce it; mocks are not proof of actual transport/hardware. A suite pass alone
does not establish fault detection. Existing individual evidence is labeled by
revision/property; absent observed implementation faults, detection strength is
UNCONFIRMED rather than passed. No all-module mutation platform is warranted for
this directed read-only classification. That is a deliberate difference from a
mutation-coverage campaign, not a substitute claim of equivalent assurance.

Sources: https://docs.pytest.org/en/stable/example/parametrize.html ;
https://docs.pytest.org/en/stable/how-to/monkeypatch.html ;
https://cosmic-ray.readthedocs.io/en/stable/index.html .

## Construction axiom-check
|Provision|Determinate question -> result and location|
|---|---|
|1 Truth|Can test count/pass be promoted to necessity/strength? CONFORMS: direction/boundary requires source evidence per case; absent fault evidence marked unconfirmed.|
|2 Adaptive cognition|Can a curated test inventory stand as coverage fact? CONFORMS: actual pytest collection joined to generated AST inventory, judgments remain explicit findings.|
|3 Antifragility|Are provider failures dismissed because data vary? CONFORMS: real counterpart/live boundary traced before phantom classification.|
|4 KISS|Does this add testing/runtime mechanisms or a count quota? CONFORMS: read-only audit and proposed reductions only.|
|5 Boundaries|Can audit execution mutate canonical data or read as deployment? CONFORMS: existing raw-root isolation, effort scratch; no code/data/hardware/fault changes.|
|6 Maintenance|Are tests judged apart from consumers/owners? CONFORMS: current call paths and contracts accompany each recommendation.|
|Preamble|Does scope exceed the operator's question? CONFORMS: one finite per-case analysis and required two-family review, no test rewrite/coverage campaign.|
