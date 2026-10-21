# Backup unit isolation

Operator: Bryan08:53/08:55EDT2026-10-21, verbatim direction relayed in
broker39b98961-fd07-4074-a9ca-167431e169ee. Try every unit independently,
verify each, record each accurately, continue after failures. Plan transmitted
before mutation in5e2c04db-92eb-471f-b8bc-0ffb71db6a30. Baseee81559.
Paired shared increment:fix/backup-unit-isolation,base60a8702.

## Plan and C declaration

Durable backup runtime. k fires: false backup assurance/data loss can be
silent or irreversible. Keep the existing per-source lifecycle in place and
bound each source attempt independently inside the existing loop.
Every configured source is attempted, its actual verified/failed or
partial result retained, and the existing manifest written after attempts even
on failure. Any failure remains nonzero at CLI/systemd. Verified sibling bytes
must remain accurately recorded. Existing dry-run/retention/restore contracts
and configured source order remain; no retry framework, store or schedule.
Manifest is a backup verification record, not canonical provider data.
Revert paired code increment; do not rewrite source or remote history.

Use existing shared replication result/error/manifest owners rather than a
parallel transport. Current primary rclone documentation and installed help
confirm append-only initial-size transfer, while shared prefix+progress proof
remains necessary: <https://rclone.org/local/#local-no-check-updated>.
Observed05:23 copy error aborted the source loop and suppressed the manifest.

## Construction axiom-check

| Axiom | Result | Content/construction |
|---|---|---|
| 1 Truth | CONFORMS | Preserve individual verified/failed outcomes |
| 2 Cognition | CONFORMS | Iterate actual configured sources |
| 3 Antifragility | CONFORMS | Isolate observed source failure |
| 4 KISS | CONFORMS | Existing result/manifest/source loop |
| 5 Boundaries | CONFORMS | Failure recorded plus nonzero CLI |
| 6 Maintenance | CONFORMS | Retain lifecycle, update consumers |
| Preamble | CONFORMS | Real skipped source/unrecorded delivery |

Questions: can errors erase proven facts, can a curated membership stand as
fact, can one source failure suppress others, does any mechanism exceed the
observed need, can partial success read as full success, and are changed
responsibilities kept cohesive? Verify implementation from actual execution.

## Verification and review obligations

One real first-source failure still permits raw capture, records both outcomes
and exits nonzero; existing dry-run/retention/source-immutability tests remain.
Full canonical suite/Ruff with branch shared preloaded via pytest-p shared and
trace-config provenance, not live shared accidentally imported by hardcoded
test paths. Observed failing controls in real source at named revision.
Whole paired delta:independent Astra/OllamaGLM, author adjudication plus
axiom/adversarial audit, then PiClaude in existing round. No new round without
named defect class. No PR, merge or live deployment before Bryan verdict.

PiClaude plan reviewdebff661: unnecessary helper extraction and extra source
order cases CONFIRMED and removed before review freeze. Demand to omit spawned
independent review REFUTED: author plus external PiClaude does not satisfy k or
Bryan's explicit in-family/GLM mandate. No repeated review round is added.

## Implementation audit and finding dispositions

The initial whole paired review used shared1fc4b85 and enviroplus241e787.
Astra executed the dry-run regression and staging-boundary failure; GLM5.3
independently found the dry-run regression. Both are CONFIRMED and corrected:
failed dry-run outcomes are retained and return1 without writes; the existing
staging mkdir/chmod now belongs inside the database source attempt, so its
failure cannot prevent raw replication. These are the only remaining defect
classes for the bounded corrective review of the whole final artifact.

GLM's missing verification-mode record is CONFIRMED: initial dispatch preceded
the recorded implementation check. The table below closes the omission; it
does not retroactively make that dispatch compliant. GLM's changelog observation
is CONFIRMED but closed without action: no project authority requires dated
header updates, the current descriptions remain accurate, and Git records this
delta. Historical changelog entries are not current runtime assertions.

GLM's claim that one unreadable file aborts remaining rclone batch siblings is
REFUTED by actual execution: one chmod000 file plus16 healthy files, more than
the native transfer slots, produced nonzero permission-denied transport while
all16 healthy files landed, were independently proved and retained in the
partial result. Method /tmp/backup-batch-isolation-check.py and result JSON
are retained with the check evidence in Git notes. This does not claim that
a total network failure permits remote delivery.

## Verification-mode axiom-check

| Axiom | Result | Content/construction |
|---|---|---|
| 1 Truth | CONFORMS | Actual source results, no invented verification |
| 2 Cognition | CONFORMS | Config iteration, measured file classification |
| 3 Antifragility | CONFORMS | Growing files, independent staging failure |
| 4 KISS | CONFORMS | Existing loop and replication owner |
| 5 Boundaries | CONFORMS | Failed results and nonzero exits |
| 6 Maintenance | CONFORMS | Paired transport/consumer contract updated |
| Preamble | CONFORMS | Observed failure, no speculative mechanism |

Determinate questions and actual content: (1) can a failure become verified
success? shared `replicate_tree` computes verified from proofs/errors and raises
with partial evidence; `run` records it and returns1. (2) does curated membership
replace discovered data? `run` reads cfg.sources; shared enumerates actual paths
and probes actual remote bytes. (3) can growing input or failed database staging
prevent healthy sibling capture? the documented tree-only flag permits ongoing
append; `run` puts staging preparation inside the database try. (4) does any
added mechanism lack an observed failure or live input? the flag, containment,
partial result and manifest all address the observed05:23 failure; helpers,
extra permutations, new stores, retries and transport frameworks are absent.
(5) can any changed boundary hide failure? ReplicationError remains raised,
main reports nonzero, and invalid-kind dry-run returns1 without writes.
(6) are both sides of the changed seam and current claims aligned? the only
runtime consumer retains the shared partial result; config principles, manifest
docstring and aggregate-exit tests follow the changed contract.

Executed properties: the real growing-file test and partial-copy proof test
each failed under actual source violations and passed after restoration at the
initial frozen shared head. The source-loop control likewise failed when the
old bail-out was restored. The corrected staging/invalid-dry-run tests pass in
the focused20-test lifecycle suite. Exact final-head canonical checks and
revision-qualified violation results are attached as Git notes, not inferred
from these counts. The CLI/rclone checks use temporary local remotes and real
source failures; they do not certify Google Drive or deployed service behavior.
