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
