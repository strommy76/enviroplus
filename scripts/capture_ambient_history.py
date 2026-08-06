"""Resumable, crash-safe raw capture of Ambient history.
Manifest row is appended IMMEDIATELY after each file write, so an interrupted run
never orphans bytes. Skips days already captured. Writes NO database."""
import json,time,hashlib,urllib.request,urllib.error,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,"/home/pistrommy/projects")
from shared.raw_retention import scrub_body
OUT=Path.home()/"projects/enviroplus/raw-capture/ambient"; MAN=OUT/"manifest.jsonl"
env={}
for l in (Path.home()/"projects/enviroplus/.env").read_text().splitlines():
    l=l.strip()
    if l and not l.startswith("#") and "=" in l:
        k,_,v=l.partition("="); env[k.strip()]=v.strip().strip('"').strip("'")
have={p.stem for p in OUT.glob("*.json")}
def append(rec):
    with MAN.open("a") as f: f.write(json.dumps(rec)+"\n"); f.flush()
now=datetime.now(timezone.utc); empties=0; back=0; CAP=400; new=0
while empties<3 and back<CAP:
    t=now-timedelta(days=back); day=str(t.date()); back+=1
    if day in have: continue
    url=(f"https://api.ambientweather.net/v1/devices/{env['AW_MAC']}"
         f"?apiKey={env['AW_API_KEY']}&applicationKey={env['AW_APP_KEY']}"
         f"&endDate={int(t.timestamp()*1000)}&limit=288")
    rec={"provider":"ambient","key":day,"endDate_utc":t.isoformat(),
         "captured_utc":datetime.now(timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(url,timeout=30) as r: raw=r.read()
        d=json.loads(raw)
        if d:
            # Same scrub the live collectors apply. Without it this one-off
            # writes a device credential straight into the canonical tier and
            # from there to the offsite copy.
            stored, scrubbed = scrub_body(raw)
            (OUT/f"{day}.json").write_bytes(stored); empties=0; new+=1
            rec.update({"status":"ok","file":f"{day}.json","records":len(d),
                        "fields":len(d[0].keys()),"bytes":len(stored),
                        "sha256":hashlib.sha256(stored).hexdigest(),
                        "newest":d[0].get("date"),"oldest":d[-1].get("date")})
            if scrubbed:
                rec["scrubbed_keys"]=sorted(set(scrubbed))
                rec["sha256_as_received"]=hashlib.sha256(raw).hexdigest()
            print(f"  {day}  rec={len(d)} fields={len(d[0].keys())}",flush=True)
        else:
            empties+=1; rec.update({"status":"empty","records":0})
            print(f"  {day}  EMPTY ({empties}/3)",flush=True)
    except urllib.error.HTTPError as ex:
        rec.update({"status":"http_error","code":ex.code}); print(f"  {day} HTTP {ex.code}",flush=True); time.sleep(10)
    except Exception as ex:
        rec.update({"status":"error","error":type(ex).__name__}); print(f"  {day} ERR {type(ex).__name__}",flush=True)
    append(rec); time.sleep(2.5)
print(f"DONE new={new} deepest={day}",flush=True)
