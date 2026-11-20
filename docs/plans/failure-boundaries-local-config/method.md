# Local dashboard configuration isolation — November19

Authority: broker f0312af1-c3b5-4434-9c05-437899059f3c, Pi Claude sent
2026-11-20T03:55:35.358920Z, relaying Bryan's November19 22:55 direction.
Baseline: enviroplus aeee648cf9e996536382886a709eb7f209079298.
Shared dependency: f42d0c4b64dccf2e466f0f6751ba3cb30a90e911.

Method: add test_bad_dashboard_config_keeps_provider_results without changing
provider_health.py. Populate real isolated SQLite provider tables with current
observations; give the actual main entrypoint malformed dashboard JSON and a
native-shaped loaded/enabled producer. Only environment acquisition and the
native-manager read are substituted outside the config/SQL/CLI property. The
old main raises JSONDecodeError before emitting any results: old-order.log.
Then move the local read/calculation into check's existing active-local try,
remove the coupled helper and repair its existing test/metadata dependents.

Commands (run in this candidate checkout):
```
PYTHONPATH=/home/pistrommy/projects/.tmp/backup-config-fleet-20261118/test-imports:/home/pistrommy/projects/.tmp/hardcoded-config-audit-20261119/enviroplus-worktree /home/pistrommy/.virtualenvs/pimoroni/bin/python -m pytest -q tests/test_provider_health.py::test_bad_dashboard_config_keeps_provider_results
# baseline implementation, new regression: exit1; 1 failed
PYTHONPATH=/home/pistrommy/projects/.tmp/backup-config-fleet-20261118/test-imports:/home/pistrommy/projects/.tmp/hardcoded-config-audit-20261119/enviroplus-worktree /home/pistrommy/.virtualenvs/pimoroni/bin/python -m pytest -q tests/test_provider_health.py
# corrected implementation: exit0; 15 passed in0.33s
/home/pistrommy/projects/stocks/.venv/bin/ruff check provider_health.py tests/test_provider_health.py
/home/pistrommy/projects/stocks/.venv/bin/ruff format --check provider_health.py tests/test_provider_health.py
# both exit0; all checks passed; 2 files already formatted
```

The regression observes every policy lane, actual provider timestamps with no
provider problem, local JSONDecodeError/unreadable, and nonzero CLI status.
The old implementation's failure establishes sensitivity to this ordering
violation only; it does not qualify unexecuted failure modes or deployment.
No production DB, service, hardware or data was changed. No unchanged suite or
new review-seat round was run; Pi directly verifies this directed fold.
