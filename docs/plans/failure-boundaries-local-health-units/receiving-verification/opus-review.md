10:34 PM EST · opus-review (Claude Opus 5.5, independent seat)

## Verdicts
| Repo | Rev | Verdict | Block? |
|---|---|---|---|
| Shared | ca500fe..be66533 | ACCEPT | no |
| Stocks | 4657b0c..e224939 | ACCEPT | no |
| Enviro | 2878e61..0cb2d10 | ACCEPT WITH CHANGES (E1, E2; E3 before deploy) | no; E3 gates deployment, not landing |

## Findings
| repo file:line | status | failure scenario | minimum correction |
|---|---|---|---|
| E1 enviro provider_health.py:57-58 (`LoadState != "loaded" or UnitFileState != "enabled"` -> ValueError) | CONFIRMED (built: masked/masked, loaded/linked, loaded/enabled-runtime each return `observation_unreadable`) | `systemctl mask enviro_dash` is systemd's standard way to keep hardware that is disconnected from ever starting. The read succeeds but is reported as "unreadable", so main() exits 1 and OnFailure pages on every 60 s run for as long as it stays masked. Disconnecting hardware then causes a persistent failure, which breaks the 22:07 decision, and the label is wrong (the read did not fail). `linked` (linked but not enabled) is not enabled in substance either. | Treat LoadState=masked (and optionally UnitFileState=linked) as `active=False` with detail, in the existing disabled branch. One condition. Cost: about 1 line and 1 test row. Unknown states can stay unreadable. |
| E2 enviro tests/test_service_units.py:22-31 | CONFIRMED (mutation M4) | The test checks only ExecStart[0], WorkingDirectory, PYTHONPATH and Documentation. Mutation M4 put `/home/pistrommy/projects/enviroplus/config/backup.json` back as a literal in enviro_backup.service.in's ExecStart argument, and all 13 tests passed. A literal root in any other argument or directive goes unseen. This is the exact violation "NO hardcoding" targets. | Also assert, for every rendered unit, `str(source) not in content` (source = real checkout root) and `"@" not in content`. Cost: 2 lines. |
| E3 enviro rename of airnow_wx/ambient_wx/nws_wx.service -> config/unit_templates/*.in | CONFIRMED (live, read-only: /etc/systemd/system/{airnow,nws}_wx.service are symlinks into ~/projects/enviroplus/<name>.service; prod checkout 0350abe tracks them) | Pulling this into the prod checkout deletes 3 unit files that live units link to (and .gitignore now hides the regenerated ones). Running collectors keep going, but after the next daemon-reload or reboot all three are not-found. They never start, so OnFailure never fires, and enviro_provider_health is not-found on this host too. Provider collection is lost silently until someone runs `python -m service_units`. | Deployment record: run `PYTHONPATH=.. <venv>/bin/python -m service_units` in the same step as the checkout, before any daemon-reload, and verify LoadState. No code change. Separate from landing (d). |
| E4 enviro provider_health.py:26-38, 103 (`load_policy` reads CONFIG_PATH before any lane) | CONFIRMED by reading | If the capture config is missing or bad (for example while hardware is being reconfigured), main() crashes. The NWS, AirNow and Ambient results are lost, which goes against "a broken query belongs to its lane". The failure is loud, not silent. | Optional: compute the local allowance inside the lane's try block. Low; the adjudicator weighs it. |
| E5 enviro test_service_units.py:14 + enviro_backup*.in `Documentation=file://@ROOT@/...` | CONFIRMED (`systemd-analyze verify`: "Invalid URL, ignoring: project/config/backup.json") | The test's own root contains a space ("relocated project"). It passes under ConfigParser, but systemd splits the URI at the space. The test overclaims relocatability; the production path has no space, so this is cosmetic. | Drop the space from the test root, or render via `root.as_uri()`. Low. |
| S1 shared systemd_units.py:7-11 (`root=None` skips both substitutions) | CONFIRMED by reading | A caller that omits root writes a literal `@PYTHON@` into a unit file. It shows up only when systemd starts the unit, and no test covers it. @PYTHON@ does not depend on root at all. | Optional: always substitute @PYTHON@, or raise if `@ROOT@` remains. Low. The Stocks callers (rebalance/reconciler) pass no root and carry no placeholders today. |
| T1 stocks tests/test_daily_capture_completion.py:141 (only test that sees the SELECT column) | UNCONFIRMED | Mutation S3 (drop `completed_at` from the SELECT) can only be caught by this Postgres test, which I could not run under the no-Postgres constraint. The pure tests feed a hand-built `completed_at`. | None if the author's retained control log is accepted. The adjudicator should confirm it from `stock-missing-query-clock-control.log`. |

Mutation record (each mutation reverted after its run). Stocks: restoring the `"acquired_at" in item` exemption made 3+ test_data_freshness cases fail. Setting the failed clock to checked_at (a fabricated timestamp) made `*_no_timestamp_stale` fail. Enviro: literal interpreter in nws, literal root in airnow WorkingDirectory, and literal root in ambient PYTHONPATH each made 1 test fail. not-found reading as active failed, unknown state read as disabled failed, and inverting the enabled gate made 2 fail. **The literal root in the backup ExecStart argument passed (E2).** Shared: dropping the @ROOT@ substitution made both the Shared and Enviro tests fail. Dropping `root=` in backup_units was caught only by the Enviro test; Shared's own suite passed. Resolving sys.executable to its realpath went undetected, because the test interpreter path does not exist.
Directed outcomes held: no timestamp is fabricated (`attempt_completed_at` is kept separate from `acquired_at`, and the SELECT's `completed_at<=%s` excludes NULL). Not-found or disabled is inactive with detail. Enabled with stale readings gives `observation_stale`. A systemctl CalledProcessError or OSError gives unreadable. No literal interpreter or root is left in any `.in` file. The one remaining copy is docs/rollback/display-spi/enviro_dash.service, a rollback copy and not a template.

## Axiom rows
| Axiom | Result | Location / construction |
|---|---|---|
| 1 Truth | CONFORMS | Stocks keeps `attempt_completed_at` separate from `acquired_at`, and the S2 mutation (fabricated clock) is caught. Enviro reads native systemctl state, not a flag. |
| 2 Cognition | CONFORMS | Units are discovered by globbing templates. `producer_unit` is one binding that cannot be derived. The interpreter and root come from the rendering process. |
| 3 Antifragility | VIOLATES (E1, minor) | provider_health.py:57: masking hardware, a native change, produces a persistent page. Adding or disconnecting hardware "must not cause persistent failures". |
| 4 KISS | CONFORMS | One column, one systemctl read, a 4-line renderer extension. The optional `root` in S1 is justified by Stocks callers that pass none. |
| 5 Boundaries | UNCONFIRMED | Inactive, unreadable and stale stay distinct. But a successful read of a masked unit is labelled unreadable (E1), and the E3 deploy path fails without a signal. |
| 6 Maintenance | CONFORMS with E3 caveat | provider_health_units was removed and its consumers and docs migrated. The live symlinks need the regeneration step in deployment. |
| Preamble | CONFORMS | No mechanism beyond the folds. The E1/E2 fixes cost 1-2 lines each. |

## Input limits
- Read the packet, prompt, AGENTS.md, both skills, the full sources at the named revisions, and both plans' fold sections.
- Not run: the Postgres-backed stocks test (T1), because of the constraint against touching Postgres.
- Live state: one read-only `systemctl show` and an `ls` of /etc/systemd/system. Nothing was mutated, and no secret values were read (a key-count grep only).
- The stocks range also contains a7d7f63/fffcc84 (dependent-test repairs that predate the fold). I checked that they pass but did not judge them against the 22:00 direction.
- No prior review was available to compare against.
Would I block: no. E1 and E2 are cheap fixes the adjudicator can decide on, and E3 must sit in the deployment step.
