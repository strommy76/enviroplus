# Native SCD41 calibration documentation

## Plan and authority
Bryan directed calibration against the TMP119 reference on October31,2026.
This landing records the two documentation updates from that completed native
operation. No runtime code, automatic compensation, calibration execution, source
data, configuration or service behavior is changed by this PR. Lifetime is durable
documentation; a false source description could mislead silently. Revert the two
documents to undo this documentation change, without rewriting sensor history.
Only Bryan decides landing after the canonical checks.

## Source, effect and review
The private analysis/method, original observations, actual driver outcomes and
separate source/effect review records are preserved locally in Git tag
archive/tmp119-calibration-analysis-20261031 (eb1296e). They are intentionally not
in this public branch's ancestry. Canonical acquisition records remain authoritative;
SQLite remains derived. No private household observation history is published.

Whole author reviews by spawned OpenAI Astra and GLM-5.3/Ollama were adjudicated
in that record. PiClaude's separate two-family receiving accepted the analysis and
observed effect in broker50de6274-a64f-4bbc-ae46-a551f313181f, sent October31
23:59EDT. Source and hardware readback support the bounded native adjustment,
not long-run absolute accuracy, independent humidity accuracy, thermal equilibrium
or power-cycle verification. No further corrective review class was identified.
The remaining repository-hygiene correction is this minimal branch/PR rather than
uncommitted tracked documentation on canonical main; operator photos are preserved.

## Axiom check, construction and final documentation
|Provision|Result and source|
|---|---|
|1 Truth|CONFORMS: README and PROJECT-CONFIG describe native compensation and reported RH; no extra software correction/accuracy claim.|
|2 Adaptive cognition|CONFORMS: no new rules, curated fact inventory or runtime mechanism.|
|3 Antifragility|CONFORMS: original source events/history and private Git provenance preserved; no replay.|
|4 KISS|CONFORMS: only two existing docs plus this landing/provenance record; no numerical campaign in the public branch.|
|5 Boundaries|CONFORMS: completed native operation, documentation, publication and operator landing are distinct.|
|6 Maintenance|CONFORMS: current sensor-role descriptions updated together, canonical tracked edits moved to their reviewed branch.|
|Preamble|CONFORMS: correct observed documentation drift without adding a runtime path or repeating the calibration.|

Canonical validation result is recorded in this PR after execution. Passing existing
tests is a compatibility check, not independent evidence of physical calibration.
