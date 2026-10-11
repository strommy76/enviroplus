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
