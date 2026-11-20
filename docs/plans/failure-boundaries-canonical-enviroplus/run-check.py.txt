"""One-use final-head canonical commands, supervised by native qual-* units.

Authority: receiving3a8e77e4/2fc0e439. No production changes. Short-lived
qualification method/results are archived in the same T3 artifacts afterward.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, os, subprocess, sys, tempfile, time
H=Path('/home/pistrommy/projects/.tmp/hardcoded-config-audit-20261119')
B=H.parent/'backup-config-fleet-20261118'
name,expected=sys.argv[1:];root=H/(name+'-worktree');out=Path(__file__).resolve().parent/name
out.mkdir()
actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert actual==expected
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
shared=B/'shared-worktree'
python=str(root/'.venv/bin/python') if name=='stocks' else '/home/pistrommy/.virtualenvs/pimoroni/bin/python'
ruff='/home/pistrommy/projects/stocks/.venv/bin/ruff'
tmp=Path(tempfile.mkdtemp(prefix='qual-'+name+'-',dir='/tmp'))
bindings={'PYTHONPATH':str(B/'test-imports')+os.pathsep+str(root),'PATH':'/home/pistrommy/.local/bin'+os.pathsep+os.environ['PATH'],'DUPLICACY_TEST_BINARY':str(B/'tools/duplicacy_linux_arm64_3.3.0'),'TMPDIR':str(tmp),'PYTHONUNBUFFERED':'1'}
record={'authority':['3a8e77e4','2fc0e439'],'repository':name,'revision':actual,'shared_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=shared,text=True).strip(),'started_utc':datetime.now(timezone.utc).isoformat(),'explicit_nonsecret_bindings':bindings,'steps':[],'status':'running'}
def save(): (out/'result.json').write_text(json.dumps(record,indent=2)+'\n')
save()
args=['src/','scripts/','tests/'] if name=='stocks' else ['.']
pytest_args=['--basetemp='+str(tmp/'pytest'),'--junitxml='+str(out/'pytest.xml')]
bootstrap='from pathlib import Path;import shared;assert Path(shared.__file__).resolve().parent==Path('+repr(str(shared))+');import pytest;raise SystemExit(pytest.main('+repr(pytest_args)+'))'
commands=[('ruff-check',[ruff,'check',*args]),('ruff-format',[ruff,'format','--check',*args]),('pytest',[python,'-c',bootstrap])]
container='stocks_issue176_test_pg';owned=False
try:
 if name=='stocks':
  original=subprocess.check_output(['docker','inspect','--format','{{.State.Running}}',container],text=True).strip()
  assert original=='false','isolated test database belongs to another run'
  subprocess.run(['docker','start',container],check=True,stdout=subprocess.DEVNULL);owned=True
 for label,argv in commands:
  print(name,label,'started',flush=True);start=time.monotonic()
  with (out/(label+'.log')).open('x') as log:
   result=subprocess.run(argv,cwd=root,env=os.environ|bindings,stdout=log,stderr=subprocess.STDOUT)
  record['steps'].append({'stage':label,'argv':argv,'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-start});save()
  print(name,label,'exit',result.returncode,flush=True)
  if result.returncode:raise SystemExit(result.returncode)
 record['status']='passed'
except BaseException as exc:
 record.update(status='failed',exception_type=type(exc).__name__,exception=str(exc));raise
finally:
 if owned:
  subprocess.run(['docker','stop',container],check=True,stdout=subprocess.DEVNULL)
  record['test_database_final_running']=subprocess.check_output(['docker','inspect','--format','{{.State.Running}}',container],text=True).strip()
 record['completed_utc']=datetime.now(timezone.utc).isoformat();save()
print(json.dumps(record),flush=True)
