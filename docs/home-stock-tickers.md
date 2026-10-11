# Home ticker panels and phantom datasource retirement

## Directed increment — 2026-10-11

Pi-Claude relayed Bryan verbatim in broker message
fd98738c-845f-4489-947a-ea0c5d2c6ede (sent 13:09 EDT):
at 13:04 EDT, on the phantom stocks-sqlite-ds, "We can remove it since it is now
phantom"; at 13:08 EDT, on the Home stock panels, "Honestly, the only stocks
panel I use is the top one. The rest can be retired".

Input: Enviroplus 2d2a8107fc4f24c955e40cb7b33cefd8bc663118, owner
grafana/dashboards/home.json, uid home-combined-dash. Native live Home equals the
complete source except Grafana-owned id/version and source _meta. Its 59 panels
include 34 references to the absent-file datasource. The retained top stock row
contains six existing ticker stats and their 90-bar sparklines. The existing
stocks-postgres-ds serves market_data.ohlcv with ticker, bar_date (date), OHLC
(numeric) and volume (bigint). No provider acquisition or data-store change.

## Plan, C/H and boundaries

One cohesive increment: retain the six top-row stock stats, read their same
latest-90 daily-bar selection from market_data.ohlcv, return chronological
time/value frames to native Postgres Grafana, and preserve their presentation.
Remove the other 28 stock panels and their empty row headings. Compact only the
remaining layout positions; preserve all environmental panels and queries.
Remove superseded SQLite target attributes and redundant client sorting where
the Postgres time-series contract already requires chronological SQL output.

Search found no supported Home generator or migration service. Existing owner
JSON, native file provisioning and native per-UID datasource API are the
supported interfaces. Existing Grafana provisioning already omits the phantom;
no Grafana-repository implementation or new deletion helper is needed.

This dashboard configuration is permanent runtime work. One branch and PR in
Enviroplus. Failure could be silent (incorrect displayed latest values/history)
or irreversible (native deletion of a stale integration's metadata), so k fires:
whole named revision, baseline, applicable authorities and actual provider seams
receive spawned Astra/OpenAI and GLM-5.3/Ollama reviews; findings are individually
adjudicated under axiom-check, then pi-Claude reviews before a verdict. Native
checks are short-lived tools: their method, results and input revisions are
recorded here; no maintained validation framework is added.

Before deployment, execute each actual candidate target through Grafana and
compare its newest date/value and history with independent direct source reads.
Prove nonstock content remains unchanged. After source review and operator merge
verdict, publish the owner file through its existing mount/provisioner, compare
the served content, execute actual retained and environmental queries, and
inventory every served dashboard for remaining datasource references. Only then
delete stocks-sqlite-ds through its supported native API and verify GET returns
404; confirm every remaining datasource's native health. No Grafana DB editing,
service restart, query fallback or secret/data export. Native query, provisioning
or deletion failures remain failures. Distinct deployed-effect review follows.

Revert the owner JSON through Git and native provisioning if needed; before
native deletion its existing record is untouched. Native deletion is explicit
operator-directed retirement, not reversible preservation of its internal ID or
creation history. Never reconstruct authoritative Grafana/database state to
claim a lossless revert. No live provider records are deleted or reconstructed.

BTC-USD's last observed daily bar is Friday October 9 even though the instrument
trades weekends. That is a separately raised freshness observation, not authority
to add a collector/backfill change, synthesize a weekend bar or hide stale data.

## Construction axiom-check

| Axiom | Falsification question | Result |
|---|---|---|
| 1 Truth is absolute | Provider values rebuilt or substituted? | CONFORMS |
| 2 Cognition is adaptive | New curated routing introduced? | CONFORMS |
| 3 Antifragility is doctrine | Retired datasource can be reprovisioned? | CONFORMS |
| 4 KISS | New service or guard introduced? | CONFORMS |
| 5 Boundaries | Failed query/deletion reads as success? | CONFORMS |
| 6 Maintenance is directional | Unrelated ownership or collection changed? | CONFORMS |
| Preamble | Unobserved-case mechanisms admitted? | CONFORMS |

Locations: the plan retains the inspected Postgres projection and requires actual
value comparison (1); changes only the operator-selected existing UI, not a
runtime routing registry (2); removes all live references before native deletion
and verified provisioning cannot recreate the datasource (3); uses existing JSON
and native APIs without new runtime mechanisms (4, Preamble); declares native
failure and irreversible deletion boundaries (5); retains dashboard, Grafana and
market-data ownership, with environmental content unchanged (6). These admit the
execution shape, not unperformed results.

Primary contracts: [Grafana Postgres time-series queries](https://grafana.com/docs/grafana/latest/datasources/postgres/query-editor/),
[native datasource API](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/data_source/).
The installed Grafana 13.1.1 behavior remains the deployment evidence.

## Source execution and independent review — 13:19–13:25 EDT

Named implementation input: c593f1a165226842f4128ebe5357e6e2312e933e, against
2d2a8107fc4f24c955e40cb7b33cefd8bc663118. This follow-up records observations;
the dashboard bytes remain unchanged from that reviewed revision.

Complete source-object comparison: 59 panels become 26 (five retained rows,
15 environmental/system panels, six ticker stats). Exactly 28 stock panels and
five empty stock rows are removed. Every field of the 15 environmental/system
panels equals baseline except gridPos.y. All six ticker presentations match
except their deliberately replaced datasource/query and superseded sorting.
No retained rectangles overlap; no active phantom reference remains in Home.

One-time native method: load actual candidate panel targets, add their declared
panel datasource to the native request, then POST /api/ds/query to the current
TLS-verified Grafana using its private credential only in process memory. For
each ticker, execute the unchanged candidate rawSql/time_series target. Compare
all returned times/values with an independent table-format source read selecting
bar_date::text and close, ordered descending with LIMIT 90, reversed locally;
the expected UTC dates derive from the source, not from candidate output. Native
Postgres labels the schema time field `Time`; use its declared time type rather
than presuming a lowercase rendered field name. An initial method attempt used
that wrong field label and failed before reporting a pass; it changed no source
or stored rows. Run every unchanged environmental/system target through its
real SQLite plugin with the supported queryText field and its complete format
attributes; do not reinterpret or rewrite its SQL.

Observed: all six ticker targets returned 90 chronological points, with all
540 date/value pairs equal to independent direct source reads. Latest date for
each is 2026-10-09; that actual date is retained, not fabricated as current.
All 16 unchanged environmental/system queries succeeded. This establishes query
execution, not browser-rendered visuals or an environmental freshness claim.

Two negative constructions execute changes to actual target SQL through that
same native backend: replacing its relation with a nonexistent one produces
a native query failure; changing inner latest-90 selection to oldest-90 produces
a last date different from the independent source's latest date. The latter
would violate the latest-price/history contract despite returning valid frames.
These observations establish sensitivity to those actual SQL violations only;
they do not turn a configuration parse or generic test pass into wider proof.

Astra/OpenAI reviewed the entire c593f1a delta and complete source/runtime seams.
It independently executed all six targets, read all 15,947 current source rows
for those instruments in a read-only Postgres transaction, sorted each complete
history, selected latest 90 and compared all 540 returned date/value pairs:
equal, ascending, numeric and non-null. It independently confirmed exact panel
preservation, removal counts, layout and current provisioner definitions.
No confirmed dashboard defect was found; all canonical axiom questions conform.

Astra's full served-dashboard inventory found one additional substring in the
Strategies v2 historical May 6 cutover changelog. REFUTED as a live dependency:
that append-only provenance names the old transition, not a current query or
datasource reference. Do not rewrite history to satisfy a string scan.
BTC daily-bar freshness is CONFIRMED as the existing separately raised
observation; the faithful projection is not its correction. Deployment remains
UNCONFIRMED until the separate native publication/deletion checks are executed.

GLM-5.3/Ollama reviewed the complete same artifact, complete baseline, project
authorities, native provisioner/datasource files and the one-time method. It
found no candidate dashboard defect and statically confirmed the removal,
query semantics and preservation. Executed results were not yet in its packet;
its inability to independently execute this host is retained, not called a pass.
Individual finding dispositions:

- Title-to-ticker coupling in the one-time negative demonstration: CONFIRMED at
  method source, closed without action because it is not a defect in this named
  single-run outcome. The actual SPY title equals its actual query ticker, the
  completed observation is valid, and the tool has no future consumer. A
  hypothetical retitled/reused method is outside its declared short lifetime;
  no permanent mechanism or new review round is justified. The primary
  comparisons extract the actual query ticker and do not depend on title.
- Missing recorded execution output: UNCONFIRMED by GLM at its dispatch revision,
  closed here by recording the actual observations and native method/input
  provenance before deployment. No fabricated reviewer execution or pass.
- Inventory coverage beyond Home: UNCONFIRMED by GLM, independently exercised
  by Astra and the author; the pre-deletion full served-reference check remains.

### Implementation axiom-check

| Axiom | Falsification question | Result |
|---|---|---|
| 1 Truth is absolute | Times/values differ from current source? | CONFORMS |
| 2 Cognition is adaptive | New curated routing registry introduced? | CONFORMS |
| 3 Antifragility is doctrine | Candidate/provisioner recreates retired integration? | CONFORMS |
| 4 KISS | Mechanism protects an unobserved case? | CONFORMS |
| 5 Boundaries | Invalid query reads as success? | CONFORMS |
| 6 Maintenance is directional | Unrelated panel/ownership changed? | CONFORMS |
| Preamble | Mechanism exceeds demonstrated need? | CONFORMS |

Locations/constructions: all six actual Home targets and direct source content
agree through two independent native methods (1); the complete two-file source
delta adds no runtime registry or routing, only the existing operator-selected
UI (2); complete candidate/provisioning inspection removes live references and
the declared native retirement boundary requires a served recheck (3); no
service, guard, framework, dependency or collector code is introduced (4,
Preamble); actual missing-relation and wrong-history target mutations fail their
native/independent-data boundaries, with no fallback (5); complete retained
object comparison proves the bounded layout-only environmental change and
preserves existing owners, stores and schedules (6). Source conformance is not
a claim that the not-yet-deployed retirement has occurred.

## Reviewed publication and native retirement — 13:35–13:39 EDT

Pi-Claude's source review sent at 13:35 EDT covered complete e68b1c3 against
2d2a810, independently verified removal/preservation/layout and executed BTC's
exact target: 90 points, 2026-07-12 through 2026-10-09, no error. No blocking
defect was found. It clarified the existing BTC history includes weekends, then
stops at October 9: the two-day collection gap is not a Friday-only series.
That observation remains outside this retirement; pi-Claude is diagnosing it
read-only, not adding a repair to this increment.

At 13:36 EDT, pi-Claude relayed Bryan verbatim:
"Weird on the Bitcoin. Yes, let's merge 21". PR #21 landed as bb72e52.
Before publication, the current live Home still equaled the baseline owner
content. The production checkout fast-forwarded to the approved merge and its
existing mounted owner file was published through supported native
POST /api/admin/provisioning/dashboards/reload: HTTP 200, configurations reloaded.
No container or acquisition service was restarted.

After publication, every served Home field equaled the reviewed source except
native id/version and source _meta. The live UID remains home-combined-dash,
with 26 panels. Requests taken directly from the served panel targets preserved
their datasource and all query/format attributes; the SQLite frontend's required
queryText was supplied from its unchanged rawQueryText. All 22 served Home
queries passed: six stock stats each with 90 ascending points and the 16
environmental/system queries. This is native query/content verification, not a
claim of browser-rendered visual inspection.

Re-inventory of all six served dashboards found no active stocks-sqlite-ds
references, excluding only the proved historical source changelog. The exact
native datasource was then resolved by UID and type, confirmed unprovisioned,
and retired through DELETE /api/datasources/uid/stocks-sqlite-ds: HTTP 200,
Data source deleted. A subsequent GET on that UID returned 404. No direct
Grafana DB edit, sidecar operation, provider-data deletion or replacement occurred.

Every remaining native datasource health check returned HTTP 200/OK: EnviroPlus
SQLite, Lexx Postgres, PiHoleWatch SQLite and Stocks Postgres. Grafana's recorded
start time stayed 16:59:23 UTC throughout this change. The retired file-backed
integration is gone rather than having its failure suppressed; current provisioner
definitions contain no path ready to recreate it.

Distinct pi-Claude deployed-effect review was requested at 13:39 EDT. Its reply
(broker defd81da-5ae1-469f-9e65-1fc7653902ed, sent 13:47 EDT; message header
13:46 EDT) independently confirmed the native retirement: GET returns 404,
all four remaining datasources are healthy, and no active datasource object in
any of the six served dashboards references the retired UID. It executed all
22 served Home targets with their complete attributes through the native backend:
zero errors and zero empty results. This agrees with the author's deployed
content/query checks; no new defect or additional review round is indicated.

Pi-Claude's separate read-only BTC diagnosis reported 2,003 daily rows over
2,003 calendar days, 2021-04-16 through 2026-10-09, with no missing historical
dates. It identified the acquisition cutoff as latest_completed_session_date
on the NYSE calendar, delaying weekend bars until Monday's run. This refines
the earlier freshness observation: it is delayed collection, not demonstrated
historical loss. No collector repair or freshness accommodation was made here.

The authorized runtime increment is complete. This final documentation records
the observed effect and adjudication without changing the reviewed dashboard.
Scoped cleanup removes only the merged task branch/worktree and its one-time
local review/query artifacts; source, method, results and review provenance
remain in this repository and PR #21. No provider data or unrelated work is
part of that cleanup.
