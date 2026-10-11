# Display repair verification and disposition

Source revisions: enviroplus d86f867 from f6fbac8; pi-config e733d14 from25ad2058.
Native observations October11, 04:25–04:28 EDT. This record is provenance, not
configuration authority, and does not certify deployment not yet performed.

## Author verification-mode axiom-check

| Axiom | Result | Executed question and source evidence |
|---|---|---|
| 1 Truth | CONFORMS | Does desired source change another setting? Native preimage cmp identical; firmware diff only no_miso; unit alias resolves canonical source. |
| 2 Cognition | CONFORMS | Does new logic infer hardware from a roster? Whole paired diff has no inference/registry; selected CONFIG_PATH and privileged GPIO identify actual pins. |
| 3 Antifragility | CONFORMS | Does change depend on chip enumeration or duplicate transport? Native overlay parameter and existing stocks_ops_alert@ owner avoid both. |
| 4 KISS | CONFORMS | Does added mechanism lack live reachability? GPIO9 kernel claim and 69,070 immediate failures directly reach changed firmware/unit boundaries. |
| 5 Boundaries | CONFORMS | Can failure read as success in changed source? Unit propagates process failure to native alert; plans require readback/backup/postboot proof; effects pending. |
| 6 Maintenance | CONFORMS | Can a superseded source restore the defect? Pi5 file now references canonical unit; README links it; installed unit remains pending replacement. |
| Preamble | CONFORMS | Does complexity exceed observed exposure? One overlay option/native limiting/existing alert for a measured multiweek outage; no app or generic deployment code. |

Read full current AGENTS.md A–H/a–r with the whole delta. No secrets/config
selection/sensor logic/data writes changed. Full live firmware preimage under
pi-config docs/rollback/display-spi/ and actual installed unit under this repo's
docs/rollback/display-spi/ are immutable rollback provenance, not live definitions.
The unit preimage was inspected, not adopted as desired authority.

Native systemd257 verification: OLD installed unit reports unknown
StartLimitIntervalSec under Service; desired unit has no diagnostic. This observes
the original violation, but parsing alone does not prove limiting or delivery.
Selected dynamic_config.pi5.json specifies SPI0/CS1, DC GPIO9, PM not installed,
publish_s60. Existing app inserts shared-package parent path. Original readings
max(ts)=2026-09-17 00:24:27. Boot identity6597eef8-6996-40cd-81d0-d6fd907f4207.

## Independent source review

Astra/OpenAI at frozen source heads, sent04:27 EDT: no confirmed source defect.
Adjudicated at source: GPIO ownership CONFIRMED, closed by proposed firmware
change subject to actual activation. Obsolete UART dependency and lost shared
import REFUTED by unit/app source. Alert delivery and restored collection
UNCONFIRMED; keep required direct observations, never turn them green from parsing.
Reviewer's earlier backup observations superseded by native04:28:03 replication
completion, exit0 and actual healthy offsite journal. Host backup still failed
from04:09:42, exit1: gate remains closed. No residual waived by the author.

GLM-5.3/Ollama whole paired source review returned04:29 EDT, no blocking source
defect, all seven axiom rows conforming. Individual author dispositions:

1. Alleged contradictory installed unit section REFUTED. Reviewer names bytes
   35ce25662ddf2e28 but misreads their section: native and preserved preimage
   lines15/25–26 put300/5 under Service, not Unit. Native systemctl cat/show and
   systemd-analyze verify independently show ignored interval and effective10s.
   No evidence conflict exists; raw text, not its digest, determines the section.
2. Shared import regression REFUTED by enviro_dash3.py parent-path insertion,
   consistent with Astra. No correction.
3. Unreachable HTTP transport at failure time UNCONFIRMED, not a new defect
   established by source. Existing reused alert owner propagates delivery failure
   as an unsuccessful oneshot, not success; changed dashboard orders after
   network-online. No new retry/deadman mechanism or operator residual invented
   from missing review attachments. Actual dashboard delivery remains required.
4. Rate-limit sequence UNCONFIRMED until the declared real-failure observation;
   no claim that parser success proves it, no added test/failure producer.

Both families reviewed complete paired source heads d86f867/e733d14. Subsequent
commits add only this provenance and exact unit preimage; runtime bytes unchanged.
Independent raw GLM report retained beside this record; finder claims do not
override the source dispositions above. Deployed-effect review is separate and
pending. No further source round absent a named defect class.

## Activation gate update

Native host_backup rerun started04:28:23 and failed04:30:56, exit1. Journal
host_backup_sources.py:51 walk_error raised FileNotFoundError while os.walk
visited /home/pistrommy/projects/.codex. This is observed backup failure, not
an established root cause for why that path disappeared. Snapshot validation
and the required successful terminal result are absent; reboot is prohibited
by the operator's explicit gate. Raised to pi-Claude driving the backup under D;
no backup workaround/repair or phantom directory created by this change.

No desired unit/firmware has been activated and no reboot performed. Required
real-failure alert/rate-limit observation and postboot effect remain pending.

## Authorized activation, October11 04:42–04:45 EDT

Bryan renewed the direction to read and execute msg_enviro_dash_fix.md after its
gate update. Native evidence supersedes the earlier failed-gate observation:
host_backup ran04:31:19–04:39:04, inactive/dead, Resultsuccess, exit0. Actual
snapshot73072cae16d42e71cf785862064b19d0e867c5a53306d85f80dbbf8c91b36dd3
contains / and /boot/firmware. Same invocation checked5 snapshots and read97/97
sampled packs of1150 total, native no errors were found. This is sampled checking,
not an assertion every data pack was read. Stocks replication completed04:28:03,
exit0. Both required native gates satisfied before reboot.

No merge verdict inferred: PRs20/13 remain open. Directed host activation uses
the reviewed existing branches, unit source at enviroplus cb61d50 (runtime bytes
d86f867), firmware at pi-config e733d14. Do not remove these worktrees while the
installed unit depends on them; landing and final link cutover remain pending.

One-time method/result (H): native cp --preserve=all saved exact original firmware
and unit under /home/pistrommy/projects/.display-spi-recovery.FiknMd; cmp proved
both unchanged. Stop old loop; unlink only /etc/systemd/system/enviro_dash.service
after preservation; native systemctl link selects the reviewed repository unit;
daemon-reload, reset-failed once to arm the measured attempt, start at04:44:18.
Reset clears start counters, not retained journal; it is not claimed resolution.
Preboot process still failed from real GPIO contention, as expected.

Native journal proves actual OnFailure HTTP delivery at04:44:20.017218 EDT:
identityenviro_dash.service, transitionACTIVE, deliveredtrue, detailHTTP transport
confirmed. At04:44:49 retry was refused, Start request repeated too quickly;
at04:45:08 unitfailed with NRestarts1, effective interval2min/burst1. Both previously
unconfirmed delivery and limiting findings now confirmed by actual behavior.

Firmware preimage cmp passed immediately before application. Native mktemp on
/boot/firmware staged desired source; install retained root:root/mode755; cmp
verified staged bytes; mv -T atomically replaced exact config.txt; readback cmp
passed. Desired firmware is staged for reboot, not claimed already effective.

Preboot identity6597eef8-6996-40cd-81d0-d6fd907f4207. Native active lanes:
alpaca_minute_capture, market_monitor, ambient_wx, nws_wx, airnow_wx, tailscaled;
Postgres containerstocks_postgres healthy, Grafana containergrafana-grafana-1
running. Baseline max reading2026-09-17 00:24:27. Reboot explicitly directed;
postboot GPIO9 ownership, service startup, new real readings, capture/database/
Grafana/tailscale health and distinct effect review are still required. Healthy
boot timing remains provisional until measured. No backup/broker repair performed.

## Postboot direct validation, October11 04:54–04:56 EDT

Boot85dd9f70-eb19-4ba5-b531-901f88e23515 differs from the recorded preboot identity.
Privileged native GPIO9 is output, consumerenviro_dash3-st7735-dc, no longerkernel.
Firmware readback still exactly desired source, root:root755. Unit still links
the reviewed owner worktree; no alternate copied definition was installed.
Dashboard started04:48:42, readiness exited0 within that same second, active/
running with zero restarts through04:55:58. Real SQLite rows now arrive every
60–61s with temperature/humidity/pressure values; row timestamps08:53:48,
08:54:48,08:55:49 UTC agree with same native journal04:53:48,04:54:48,04:55:49 EDT.
This proves restoration on this observed boot, not a bound on all future starts.
Nominal adequacy was observed for this boot; population tail remains unmeasured.

Active native collection lanes: alpaca_minute_capture, market_monitor, ambient_wx,
nws_wx, airnow_wx. PostgreSQL containerhealthy and native pg_isready accepts;
Grafana HTTPS https://bspilhx.tail32dc7b.ts.net:3000/api/health passed trusted TLS
and returned databaseok. Tailscale BackendStateRunning, SelfOnlinetrue.
Full raw relevant observations preserved docs/reviews/display-spi-deployed-evidence.txt.

Observed Stocks startup finding: initial Alpaca attempt failed04:48:44–45 from
PostgreSQL connection refusal/closing during boot; native retry04:49:00 reached
active at04:49:02 and remained running. Its NRestarts1 is not zero and is not
hidden. Display firmware/unit do not alter this database startup boundary; raised
to pi-Claude under D, not repaired or relabeled as a loss-free start here.

Author deployed-effect axiom-check:

| Axiom | Result | Evidence |
|---|---|---|
| 1 Truth | CONFORMS | Source/readback; actual fresh rows |
| 2 Cognition | CONFORMS | Native GPIO/process, no roster |
| 3 Antifragility | CONFORMS | GPIO released; failures remained loud |
| 4 KISS | CONFORMS | Only directed native mechanisms |
| 5 Boundaries | CONFORMS | Gate, actual delivery, real recovery |
| 6 Maintenance | CONFORMS | Single linked source; landing pending |
| Preamble | CONFORMS | Observed outage resolved at source |

Questions executed against the finite deployment:1 can observed effect come from
a diverging firmware/unit or stale rows (cmp/nativecat/latest rows sayno);2 did
verification assume chip/address from a roster (privileged namedGPIO and actual
service establishit);3 did boot still leave pin conflict or swallow a failure
(display owns9, real preboot alert, startup error disclosed);4 was added machinery
unreachable or unnecessary (real failure then recovery crosses changed boundaries);
5 were gates or integration failures ignored (actual terminal backup/check,
HTTP confirmed and startup retry recorded);6 did rollout duplicate source or
retire an active dependency (single native link, no worktree removal). Preamble:
one option and existing native boundaries restore measured collection, not a
new monitoring framework. Repo landing/cutover and distinct cross-family effect
review remain pending; this observation is not the operator's merge verdict.

Distinct Astra/OpenAI effect review returned04:59 EDT against frozen paired
heads6f3da57/d65f18b; independently inspected native deployment04:58. All seven
axiom/admission rows conformed; no blocking effect defect or source correction.
Author dispositions: GPIO conflict/restart loop CONFIRMED closed by actual
deployment; merely inferred alert/limiting/collection recovery REFUTED by actual
journal and changing sensor values; physical pixel appearance and future-boot
timing UNCONFIRMED, no such success claim made. Reviewer confirmed unrelated
Alpaca startup failure/recovery, retained D escalation, no display correction.
Reviewer verified all required service/DB/Grafana/Tailscale boundaries. GLM
effect review returned05:00 EDT, all seven axiom/admission rows conforming;
no blocking defect. No extra source round or new runtime code added.

GLM effect findings individually adjudicated:
1. Required effect achieved CONFIRMED from GPIO/rows/journal/real health interfaces;
   no source correction. Nominal adequacy is one measured boot, not future tail.
2. Historical rationale remains in the limit comment CONFIRMED; a defect in the
   authorized outcome is not established. The comment explicitly says observed
   failure, not that ownership remains broken. Forward rate limiting is itself
   directed scope, and this repaired boundary was actually exercised. One admitted
   start passes this healthy boot; no observed nominal Enviro retry establishes a
   larger burst requirement. That is insufficient evidence for such a requirement,
   not proof transient failures cannot occur. Closing without code action: retain
   the declared minimum policy for the operator's merge judgment rather than add
   an unsupported retry budget. Its concrete behavior is visible: failure inside
   the window terminates after the alert rather than automatically retrying.
3. Raw evidence completeness UNCONFIRMED in first packet, closed by native05:01
   append: original-boot failure/restart-refusal lines and explicit successful
   readback cmp now in raw evidence. No behavior changed to make a check pass.
4. Stale/replayed rows, divergent unit and broken shared import REFUTED by actual
   data/source/native binding; no correction. Earlier section dispute likewise
   refuted by source and effective native properties, not a digest assertion.
5. Initial Alpaca readiness failure CONFIRMED outside this change, D escalation
   retained. Branch-linked unit/main-app arrangement is intentional pending
   landing, with identical unchanged application bytes; no cleanup until cutover.

Both required independent families completed distinct deployed-effect review;
all findings dispositioned, no further named defect class warrants another round.
Physical display appearance/future timing remain unconfirmed and are not claimed.
PRs20/13 and active owner-worktree link remain for operator merge judgment, not
silently landed under approval for reboot. External pi-Claude handoff follows.

## October 11 correction and native restart-admission verification

Pi-Claude's 06:05 EDT review of Enviro 4f63f1f / pi-config d65f18b confirmed
the single-start restriction and unused Pi5 alias. Bryan's direct direction to
make recovery antifragile and his 10:15 EDT "Yes" to retries supersede the earlier
choice to retain burst one. Revised unit admits two starts per 120-second checking
window: initial attempt plus recovery, not a lifetime attempt limit. Window and
inherited spacing are provisional for natural failed-start/recovery populations.

Independent peer findings adjudicated at actual source:

1. CONFIRMED: burst one rejects an early failed start's automatic recovery. Closed
   by burst two with unchanged native restart/alert owners; no error classifier.
   First sensor-loop/SQLite-write errors are caught within enviro_dash3.py and do
   not themselves exit. That example in the prior explanation is REFUTED; these
   checks never certify application freshness from process-active state.
2. CONFIRMED: deployment instructions need host reconciliation. README now defers
   active hardware selection to native service-manager evidence and requires the
   device/alert bindings be reconciled. Declaring desired source was not itself
   proof of a different selected runtime profile; no such authority inference is
   retained. Other-host notification success is not claimed.
3. CONFIRMED: Pi5 alias has no live consumer in Enviro/pi-config/Stocks/agent-config
   searches, excluding immutable historical records. Removed rather than kept as
   a compatibility capability. No Pi3 consumer was established; no Pi3 mutation.
4. UNCONFIRMED firmware drift, explicitly accepted as residual by Bryan's "accept"
   at 10:15 EDT, relayed by pi-Claude. Existing exact installation/readback stays;
   no monitoring/materialization framework is added.
5. CONFIRMED cosmetic joined tokens corrected in current plan headers. Historical
   raw journals/reviewer reports retain original bytes as provenance.
6. CONFIRMED: original 04:44:49 repeated failure was notification-de-duplicated;
   it did not deliver a separate terminal-lockout notification. Existing deadman
   observed Enviro recovery at 05:02:03.809360 EDT and HTTP-confirmed RECOVERED at
   05:02:04.040213 EDT. This re-arms future notification generations. Native failed
   state/journal identifies lockout; no claim the initial page distinguishes phases.
7. Cutover explicitly fast-forwards clean main checkouts to merged revisions before
   exact source comparisons and native linking. No worktree cleanup before proof.

Method (H), Enviro runtime e82cf8c, native systemd 257, 10:30:28–10:31:58 EDT:
three disposable `systemd-run` services carry Type=simple, User=pistrommy,
Restart=on-failure, RestartSec=30 and StartLimitIntervalSec=120s, matching source.
Recovery and old-policy control commands are `/bin/sh -c 'if [ -e "$1" ]; then
exec /usr/bin/sleep infinity; fi; touch "$1"; exit 1' sh MARKER`, with separate
markers in /tmp/enviro-restart-verification.Kvrhso. Repeated-failure command is
/usr/bin/false. No production hardware/DB/provider command or OnFailure alert is
used: only the supervised process/device/notification paths are substituted,
outside the native restart-admission property. A nonzero startup exit is an actual
counterpart outcome proven by the original GPIO failure, not a new runtime producer.

Observed results, not inferred from the intended policy:

| Native check | Burst | Actual result |
|---|---|---|
| enviro-restart-recovery-verification | 2 | Running after restart at 10:30:58 |
| enviro-restart-lockout-verification | 1 | Recovery refused at 10:30:58 |
| enviro-restart-repeated-verification | 2 | Third start refused at 10:31:28 |

Old-policy and recovery commands differ only in native burst value; old burst one
fails the recovery property while the revised field admits it. Repeated exits
cross actual native failed/"Start request repeated too quickly". This proves only
native admission/termination, not natural fault likelihood, recovery-duration
adequacy, healthy sensor semantics, or actual notification delivery. Journals
and exact invocations remain in the host journal; original real alert and changing
sensor-row evidence remain separate. Completed fixtures are stopped/reset and
removed by native systemd; no disposable service is retained in the product.

Verification-mode axiom-check against the complete paired delta and native result:

| Axiom | Result | Executed question and location |
|---|---|---|
| 1 Truth | CONFORMS | Unit fields match native controls; firmware/data unchanged; README defers live selection. |
| 2 Cognition | CONFORMS | enviro_dash.service admits actual exit outcomes; no cause whitelist or inferred profile. |
| 3 Antifragility | CONFORMS | Native isolated failed exit recovers; repeated rapid exits remain failed; no success fallback. |
| 4 KISS | CONFORMS | One burst-field correction; alias deleted; no retained framework, fixture or new service. |
| 5 Boundaries | CONFORMS | Native recovery/refusal observed; journals/OnFailure distinct; exact cutover/revert declared. |
| 6 Maintenance | CONFORMS | Current plan/README align; unused alias removed; live worktree retained until cutover. |
| Preamble | CONFORMS | Changed admission has observed old-policy violation and native recovery; no speculative mechanisms. |

Population adequacy remains UNCONFIRMED as explicitly marked at definitions.
Current live process/readings are verified independently; source edits alone are
not claimed as an activated policy. The next review class is the corrected restart
admission, value derivation, alias removal, host authority and truthful evidence
contracts across the whole paired artifact, not a new speculative campaign.
