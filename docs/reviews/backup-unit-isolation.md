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
| 6 Maintenance | CONFORMS | Extract existing lifecycle, update consumers |
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
