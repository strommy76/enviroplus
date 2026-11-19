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
|k | OpenAI Astra and GLM whole-artifact seats reviewed the initial implementation. Every finding is adjudicated below. Corrected recency/required-policy and driver-init/bootstrap boundaries are the only remaining source review class; receiving and deployed-effect review remain separate. |
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
- Independent seats: complete original reports are retained beside this artifact; findings and corrective evidence are dispositioned below. Final canonical and receiving review remain outstanding.

## Independent findings and author dispositions — November 19

Original reports apply to Stocks0006b6f / Envirof088d52. Their blanket
conformance claims, and this artifact's prior conformance claims at those heads,
are superseded by the confirmed defects below. Current axiom rows describe the
corrected implementation; they do not retroactively certify those revisions.

| Seat / finding | Content adjudication and disposition |
|---|---|
| Astra1 / GLM1 startup Shared import | CONFIRMED by actual clean subprocess import. Folded and closed at source: native service declares the same sibling PYTHONPATH seam as existing services; documented renderer invocation declares PYTHONPATH=... No source path injection or duplicate resolver. Restoringf088d52 service makes the new clean-child test fail with ModuleNotFoundError; restored unit imports and the documented real renderer succeeds. |
| Astra2 driver SystemExit | CONFIRMED from installed gpiodevice and capture execution. Folded: only the hardware observation/display boundary translates driver SystemExit into retained device failure; storage/application shutdown behavior is not wrapped. Both actual capture entrypoint cases fail atf088d52 and preserve sibling rows corrected. |
| Astra3 latched incomplete gas setup | CONFIRMED using the actual installed gas.py. Folded: existing gas setup/available/cleanup/reload interface retries incomplete initialization on a later normal read; a successfully established heater handle survives later transient measurement errors. Actual driver setup mode/GPIO failures fail atf088d52 and corrected execution records no fabricated first reading, one valid heater claim, and live sibling readings. No retry service/private driver flag mutation. |
| Astra4 NWS/AirNow timestamp-only returns | Behavior CONFIRMED; claim of an E2 defect REFUTED for the accepted freshness contract. Existing collectors/contracts accept explicit NULL measurements as provider statements; E2 checks age of those accepted statements, not downstream measurement fitness. No live contrary occurrence or required-field contract was established. Closed without action; no new completeness whitelist. Ambient differs because its existing outdoor measurement roles define the explicitly directed console-only exclusion. The report's axiom1 timestamp-only clause does not override those contracts. |
| GLM2 immediate boot check | Behavior CONFIRMED, defect claim REFUTED for the authorized outcome: old/missing observations really are unavailable after downtime. Closed without action. A conventional startup grace would hide a real failure; no evidence justifies delaying detection. |
| GLM3 invalid configured timezone | Loud config error CONFIRMED, defect claim REFUTED under the plan's explicit shared-config-fails-loud contract. Closed without action; no extra KeyError guard to treat policy defects as provider read failures. |
| GLM4 rejected no-op control | CONFIRMED honest provenance: initial exit0 mutation did not alter the intended code; it is retained and rejected. Actual exit1 control is separate. No correction required. |
| GLM5 estimate binding | CONFIRMED same public SQLITE_PATH owner for estimate and capture. Closed without action: no competing source; adding a mirror assertion would add no independent property. |

Remaining class for bounded current-revision review: driver initialization lifetime,
GPIO failure isolation, and native/bootstrap environment. The seat gets the whole
current artifact plus actual installed owners, not a patch or a desired verdict.
No hardware activation or timer/alert-effect claim follows source review.

Operator evidence: broker71f70ada, PiClaude sent November19 11:54, reports the
outdoor array is functioning but wet. The full current-day raw fit and current
16:46:47UTC read (provider-health-live-read.json) distinguish the breaker outage
from new console-only returns: Ambient last outdoor16:44 and age167.712s crossed
its provisional159.006878s bound while NWS/AirNow remained current. This is a
real missing-outdoor observation, not grounds to widen the bound or repair hardware.
The lifetime/uncertainty of the provisional bound remains declared in config.

Net runtime/config/unit lines versus 0350abe: +374/-168, net +206; excludes tests, provenance/docs and .gitignore. This size is reported, not used as a conformance proxy.
