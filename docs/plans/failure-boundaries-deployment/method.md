# Attended deployment method

The existing source plans and plan.md govern. Inputs by immutable revision are
in landing.json. GitHub supported ready/merge operations used expected_head_sha
1591d079 (Stocks346) and4f30aabb (Enviro31), merge method merge, with C/H in
both merge messages. Shared normal guarded push advanced ca500feb to f42d0c4;
existing Shared8 record carries follow-up C/H. No force push or hook bypass.

On production Shared: git fetch origin main; git merge --ff-only f42d0c4.
Existing document edit remained. On Enviro: git fetch origin main; initial
--ff-only f179669 refused the overlapping prior PROJECT-CONFIG.md edit.
Preserved exact bytes/patch privately, then git stash push naming ONLY that
path; immutable stash id retained privately in enviro-project-config-stash.txt.
Reran git merge --ff-only f179669, immediately followed by
PYTHONPATH=/home/pistrommy/projects /home/pistrommy/.virtualenvs/pimoroni/bin/python -m service_units.
No daemon-reload occurred between checkout update and generation.

Stock deploy-stocks.py.txt invokes the real deploy_unit owner; full observed
steps/PID-SHA result are in stocks-deploy-result.json and native-result.json.
Working directory is production stocks, invocation uses its lexical
.venv/bin/python and PYTHONPATH=/home/pistrommy/projects. The script's finally
restores the unrelated image held outside the clean-tree boundary.

Then from production Stocks, same Python/binding:
- -m src.services.ops.systemd_unit_reconciler --render-units
- -m src.services.ops.systemd_unit_reconciler (plan JSON)
- sudo -n env PYTHONPATH=/home/pistrommy/projects .venv/bin/python -m src.services.ops.systemd_unit_reconciler --execute
- same supported dry-run again: ok=true/actions=[]/warnings=[].

After Enviro generation, native operations:
- systemd-analyze verify enviro_provider_health.service enviro_provider_health.timer
- sudo -n systemctl --no-reload link the production Enviro provider-health service and timer paths
- existing Stock reconciler performed its initial reload and two per-link reloads
- sudo -n systemctl restart ambient_wx.service (normal shutdown completed)
- sudo -n systemctl enable --now enviro_provider_health.timer

No direct duplicate of the renderer/reconciler or trading/backup implementation
was introduced. Other live collectors remained running because their code was
unchanged. Native enable's supported reload is retained as its own owner action;
no custom controller was added to force a one-reload count.

Read-only observation methods are retained as read-native-state.py.txt and
read-capture-metadata.py.txt. The initial capture-metadata draft looked only at
NWS's cycle-level key and found0 records there. Actual NWS owner was inspected:
station captures are under nws/<configured station>. The corrected method
uses load_settings().stations and the actual reader, records root0 and station
captures distinctly, and does not report root0 as a collection outage.
Canonical records/payloads were not changed or exported. Only nonsecret capture
metadata/classification/timestamps are retained here; no URL/query/credentials.

Actual provider-health invocation (Pimoroni, production Enviro, same PYTHONPATH)
returned1 for real Ambient stale and emitted all lane results, including inactive
local HAT. The operations alert CLI (Stock .venv Python, same PYTHONPATH) with
no arguments read existing active identities before Enviro activation and after.
Only the expected Enviro health failure joined them. Native OnFailure delivery
unit exit0 is observational evidence, not human receipt.
