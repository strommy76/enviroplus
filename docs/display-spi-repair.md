# Display GPIO ownership and failure visibility

Authority: Bryan's "Yes, fix it" and "Reboot when the backup is done and validated",
relayed by pi-Claude in msg_enviro_dash_fix.md, October11. User directly instructed
pi-codex to execute that relay. Header clock is ahead of native time; native journal
timestamps govern effects and backup gates. Enviro baselinef6fbac8; pi-config25ad2058.

## One execution plan and C/H declaration

Live unit/firmware configuration; failure could silently stop collection or
interrupt boot. One branch/review artifact per owner, paired whole review by
Astra/OpenAI and GLM-5.3/Ollama, individual disposition then pi-Claude/operator
verdict. Repo changes do not claim deployed effect. Revert preserved firmware
preimage plus reboot, and preserved unit/source; keep all sensor/database data.

1. Pi-config versions the exact firmware preimage and desired config.txt; only
   spi0-2cs gains no_miso. Existing memory-controller materializer accepts single
   cmdline, not config.txt; no applicable config.txt owner was found by source search.
   No new generic materializer. Directed one-time application: preserve original,
   compare live against preimage, native same-filesystem staged install/rename,
   verify exact desired content. Commit method/results/provenance under H.
2. Make documented enviro_dash.service the reconciled Pi5 authority; Pi5 filename
   refers to it. Preserve verified deployed no-UART-bind/readiness behavior;
   move startlimit into Unit and use existing stocks_ops_alert@ OnFailure.
   Do not copy installed content as authority: analyze each difference below.
3. Preserve installed unit, stop current failed loop, install accepted repo source
   through native systemctl link, reload and start once. The existing GPIO conflict
   supplies a real failure; observe native rate limit and actual HTTP alert delivery.
   This is containment/proof, not claimed GPIO resolution. Do not erase its history.
4. Reboot ONLY after native Stocks replication success and successful rerun host
   snapshot with validation are both established. Announce host-wide interruption;
   record preboot identities and active lanes. No new backup or broker repair.
5. After reboot, inspect privileged GPIO9, actual dashboard process/SQLite readings,
   capture/Postgres/Grafana/tailscale and independent deployed-effect review.
   Missing proof fails loudly; no synthetic success or stale rows count.

## Root diagnosis and source reconciliation

Privileged native GPIO9 is consumer kernel on6.18.50. Current firmware overlay
claims MISO9; installed overlay README and upstream spi0-2cs DTS make no_miso
select only10/11. Dashboard's actual ST7735 DC is9, write-only SPI. Kernel update
association confirmed by peer history; exact upstream change mechanism unconfirmed.
Do not change library, application or kernel to hide GPIO contention.

Installed unit has actual node readiness rather than repo sleep5, and no obsolete
ttyAMA0 BindsTo. Those changes conform to optional sensor lanes and the observed
Pi5 node addresses, so preserve them. The documented generic unit formerly carried
always-restart10s; use deployed on-failure30s. Pi5 duplicate no longer can restore
the stale UART gate or misplaced startlimit. Pi3 alternative is not retired here.

Recovery policy revised under Bryan's October 11 direction to make recovery
antifragile, and his 10:15 EDT "Yes" to retries relayed by pi-Claude. Permit the
initial start and one recovery start: two is the minimum that admits recovery
without returning to the observed unlimited rapid failure loop. Retain the native
120-second checking horizon: effective startup timeout 90 seconds plus existing
restart spacing 30 seconds. This counts starts in a window, not lifetime failures;
it neither classifies errors nor claims all transient faults settle in that time.
Rapid repeated failure reaches terminal failed/start-limit-hit and existing
OnFailure; a later manual start after the window can recover. No timer or custom
recovery service is added. The horizon and inherited spacing remain provisional
pending measured failed-start/recovery intervals across boots; one healthy boot
does not settle that population. Nominal healthy runtime is not restart-counted.

Only process/startup exits cross this systemd boundary. Existing sensor-loop and
SQLite-write catches log and continue; the earlier suggestion that the first
SQLite publication necessarily causes process exit was incorrect. Healthy rows
are checked directly, not inferred from active state. No application catch or
data model change is included in this unit/firmware increment.

C/H remains long-lived unit/firmware with potentially silent collection or boot
failure. Verification uses native systemd with disposable non-production units
and the committed restart fields unchanged: a nonzero exit then a running process
must recover, repeated nonzero exits must hit the limit, and the old burst of one
must reject the recovery. Substitute only the supervised command/device and alert
paths, outside the restart-count property; no real sensor/provider outage or test
notification is induced. Preserve raw results and the exact method in this repo.
These checks certify native restart admission only, not natural transient-fault
occurrence, actual sensor health, or new alert delivery. Existing real alert proof
remains separate. Whole paired revision is reviewed by Astra/OpenAI and GLM-5.3,
findings adjudicated, then pi-Claude reviews before authorized landing.

At closure, fast-forward each clean main checkout to the actual merged revision
before comparing/linking the unit. Native daemon-reload changes policy without
restarting the healthy display process; verify GPIO, fresh rows and exact firmware.
Remove only the two clean task worktrees after no live unit depends on them. Revert
the link/policy to the preserved branch revision if cutover fails. No reboot,
private configuration, application, database or unrelated repair is included.

Bryan's 10:15 EDT "accept" (pi-Claude relay) dispositions firmware drift without
an ongoing materializer/check as an operator-owned residual. Exact installation
and closure readback still apply; no drift-monitoring capability is added.

Construction axiom-check of this correction: 1 exact unit/firmware and raw sensor
rows remain authoritative (enviro_dash.service, firmware/config.txt); 2 native
process outcomes, no exception whitelist; 3 one admitted retry tolerates an
isolated process failure while repeated rapid exits remain loud; 4 only native
burst changes, unused Pi5 alias removed, no framework; 5 native failed/OnFailure
and exact link/readback boundaries plus revert; 6 documentation no longer selects
active hardware and closure removes live task-worktree dependency. All CONFORMS
prospectively; nominal recovery-population adequacy is UNCONFIRMED, not certified.
Preamble CONFORMS: a single additional admitted start addresses the confirmed
early-failure lockout; verification exercises the changed admission property and
adds no retained runtime machinery. Future defect classes outside this plan remain D.

## Construction axiom-check

| Axiom | Result | Determinate source question |
|---|---|---|
| 1 Truth | CONFORMS | Exact preimage/desired; no reconstructed readings? |
| 2 Cognition | CONFORMS | Actual unit/GPIO prove host, no hardware roster? |
| 3 Antifragility | CONFORMS | Native GPIO role and loud unit boundary? |
| 4 KISS | CONFORMS | One overlay parameter/native alert, no framework? |
| 5 Boundaries | CONFORMS | Native failure/backup/reboot proof gates declared? |
| 6 Maintenance | CONFORMS | Duplicate Pi5 content and copy instruction removed? |
| Preamble | CONFORMS | Confirmed GPIO conflict and silent restart loop? |

Evidence locations: firmware config/overlay README, actual ST7735 constructor,
native enviro_dash unit/properties, repo service/README and backup native owners.
These are prospective admission answers, not implementation/effect certification.
A–H/a–r: scope/roles and failure lifetime above; private env/config untouched;
native owners reused; branch/artifact and cross-family review required; raw
observations not proxies; no data store created/reconstructed, no new service,
no unrelated discovery acted on. Tests certify only actual observed violations;
real pre-reboot failure/OnFailure delivery and post-reboot output are required.

Primary sources: Raspberry Pi rpi-6.18.y spi0-2cs-overlay.dts and local installed
overlays/README; systemd257 systemd.unit(5) on Unit section, startlimit and OnFailure.
