# Native reload follow-up, November19 23:30

Authority: Pi30d69d99 sent23:27:49EST, same accepted deployment scope.
Read both native backup units before action: NeedDaemonReload=yes. Their
mtime23:16:07 matches the earlier author post-deploy dry-run. Read the actual
supported run_systemd_unit_reconciler: even planning calls render_backup_units;
Shared backup_units.write_units unconditionally writes both files. Therefore
that verification action invalidated the prior manager load. This is a
confirmed execution-order cause, not a claim that the source bytes were wrong.
The more general planner write behavior is raised, not changed under this action.

Before runtime mutation, the existing plan was amended with the diagnosis,
minimum action, six prospective axiom questions and Preamble/all-section scope.
Actual command from production Stocks:
```
sudo -n env PYTHONPATH=/home/pistrommy/projects .venv/bin/python -m src.services.ops.systemd_unit_reconciler --execute
```
Exit0, actions=[], ok=true. This owner generated then performed its native
reload once. Read actual systemctl show for service/timer: both now
NeedDaemonReload=no, timer active, next elapse02:10EST. Do NOT call the generating
planner to verify again. Instead invoke the independent read-only audit:
```
PYTHONPATH=/home/pistrommy/projects .venv/bin/python -m src.services.ops.systemd_unit_audit
```
Exit2 for three pre-existing failed units and missing prior backup-completion
evidence; completion_unit_source_drift is ABSENT. Both native reload flags are
still no AFTER this audit. Original entire audit output retained without
filtering; reduced findings/result merely aid navigation. No finding, unit state,
alert or data was suppressed/reset to turn the audit green. The scheduled02:10
result stays pending. No source change, new tests/review seats or manual backup.

Verification of existing construction rows at actual owner/native results:
1 CONFORMS: actual load flags and pending completion distinct;2 CONFORMS: native
state/current config, no registry;3 CONFORMS: supported regeneration+reload loads
current source;4 CONFORMS: one owner invocation, no new mechanism;5 CONFORMS:
remaining audit failures explicit;6 CONFORMS: read-only audit leaves cached load
current. Preamble CONFORMS: no capability beyond the directed operation. Same
A-r scope; d effect evidence separate, D broader planner behavior raised, i actual
cause diagnosed, j stores untouched, l/o remaining findings not reclassified,
r no new test-property claim. Pi receives whole actual receipt for verification.
