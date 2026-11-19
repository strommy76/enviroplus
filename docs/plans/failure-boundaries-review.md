# Failure-boundary implementation review artifact

Scope: Enviro30 E1/E2 and auditF4 only; hardware stays disabled until reconnected.
Whole implementation locations: sensor_io.py/enviro_dash3.py/local_sensors.py; provider_health.py and policy/units; sqlite_backup.py.
Original direction/accepted plan: failure-boundaries.md and immutable broker IDs
there. Source review and installed-effect review are separate. No landing or
production activation is certified here; full canonical remains resource-gated.

## Implementation axiom-check

| Current axiom / falsification question | Result and content/evidence |
|---|---|
|1 Truth: does absent evidence create permission, measurements or a substitute source? | CONFORMS in inspected code: explicit observation errors/NULL and required source/policy; owning source controls in failure-boundaries-violation-observations.json. No canonical data is rewritten. |
|2 Cognition: is an inferred roster or brittle failure whitelist introduced? | CONFORMS: configured obligations/commands are policy, existing acquisition/projection/driver owners retain meaning. No discovered-fact roster is curated. |
|3 Antifragility: does one device/feed/store failure erase an independent result/job? | CONFORMS at tested code boundaries: real-source violations fail owning checks; restored source preserves siblings. Native scheduler/hardware effect remains UNCONFIRMED until deployment qualification. |
|4 KISS: does a mechanism lack its observed failure or live reaching input? | CONFORMS: issue345/30 and F4/F10 supply failures; no new retry service, data store, provider framework or hypothetical guard. Every retained test names its real violation. |
|5 Boundaries: can a failed observation read as a successful acquisition? | CONFORMS at source/checked boundaries: failed identities/details are retained and independently bad health exits nonzero. Already-owned upstream failure remains visible attribution. Installed alert receipt is not claimed. |
|6 Maintenance: does this retain superseded live logic or deepen the entrypoint gravity well? | CONFORMS in the finite change: remove fatal coupling/permissive defaults, extract actual hardware/native-job ownership, reuse rendering/projection/retention/alert seams, update current consumers. |
|Preamble admission | CONFORMS: bounded existing-path repairs prevent observed omissions or hidden failures. Deferred audits, broad .env moves, cleanup APIs and duplicate stores are excluded. |

## All execution-guidance sections

| Section | Assessment from this artifact |
|---|---|
|A | Dated original operator relays/plan acceptance bound this work; no second authorization request. Original records travel with review. |
|B | PiCodex executes assigned repos; no broker source work or reassignment. |
|C | Plan declares lasting runtime code, silent/irreversible failure, loud boundaries/revert and current primary-source premises. |
|D | Excluded findings stay excluded; SQL limits and conditional raw-path outcome are recorded rather than silently enlarged. |
|E | UNCONFIRMED verdict/deployed outcome: focused observations are evidence only; operator judgment, canonical gate and independent/receiving review remain outstanding. |
|F | No .env/credential values in code, evidence or model packet; source paths are referenced. |
|G | Mutations confined to assigned worktrees and authorized draft publication; no merge, production activation or data removal. |
|H | Runtime implementation follows declared rigor. One-use read/probe methods and results are retained as provenance, not installed services. |

## All discrete directions

| Section | Assessment from this artifact |
|---|---|
|a | Minimum named failure boundaries only; no capability inferred from a reviewer suggestion. |
|b | State stays in repo/declared live-state navigation and original broker records, not agent memory. |
|c | New names describe enduring acquisition/health/job functions. |
|d | Source review is distinct from the still-unperformed installed-effect review. |
|e | One cohesive branch/PR per accepted repository plan; draft commits are not fragmented verdict requests. |
|f | Existing PR carries C/H; operator landing after canonical success is still required. |
|g | Existing cadence/budgets retained; new freshness values derive from source settings, primary docs and retained arrivals, explicitly provisional. |
|h | Existing driver, environment, capture, projection, rendering and alert interfaces are used; no alternate engine. |
|i | Fatal dependency/iteration/init coupling, permissive policy fallback and wrong source were diagnosed before correction; no symptom suppression masquerades as health. |
|j | Canonical raw/legacy evidence unchanged and append-only; derived rows/units/health remain derived. No new durable store. |
|k | PENDING: declared OpenAI+GLM whole-artifact review at a named revision, then PiClaude receiving review. No clearance claimed. |
|l | CONFIRMED, REFUTED and UNCONFIRMED claims remain differentiated; missing power is not reported as absence. |
|m | UNCONFIRMED installed hardware/native effect; local source uses supported APIs and preserves observation contracts. No portability claim. |
|n | Per-boundary errors survive; unreadable/missing data fails health, config/storage errors still fail loudly. |
|o | Known fixes/limits have explicit dispositions; fresh reviewer findings must be adjudicated from source before verdict. |
|p | Superseded current defaults/dependencies/source literals removed. Immutable original methods/history remain evidence only. |
|q | Tests, templates, docs, generated-source consumers follow the change; runtime is not bent to preserve obsolete expectations. |
|r | Actual source controls and observed failures are retained. Invalid no-op control is explicitly rejected; no broader test property or installed effect is inferred. |

## Checks and limits

- Focused source tests/counterexamples: recorded in the per-repo observation JSON
  and the final check record added with the frozen implementation.
- Canonical Ruff/pytest, scheduler activation, hardware, deployed database/alert
  effects are separate prerequisites; unavailable checks are not a pass.
- Independent seats and adjudication: pending in this same artifact.
