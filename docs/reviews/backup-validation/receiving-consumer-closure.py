"""One-use C2 proof on committed Enviro source, native WAL/free-page mutations, canonical.
No production operation. Restore exact mutated runtime bytes in finally. Existing plan C/H.
"""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile,time
import xml.etree.ElementTree as ET
B=Path(__file__).resolve().parent
root=B.parent/'backup-config-fleet-20261118/enviroplus-worktree'
py='/home/pistrommy/.virtualenvs/pimoroni/bin/python'
owner=json.loads((B/'common-estimator-owner.json').read_text())
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
binary=B.parent/'backup-config-fleet-20261118/tools/duplicacy_linux_arm64_3.3.0'
digest=hashlib.sha256(binary.read_bytes()).hexdigest()
assert digest=='0e28cc3d943b2357136364d73a66ac82309ed9ecc36a3f9fea64b23ca1f8427c'
tmp=Path(tempfile.mkdtemp(prefix='rc-',dir=B.parent))
env=os.environ|{'PYTHONPATH':owner['isolated_parent']+os.pathsep+'/home/pistrommy/projects','DUPLICACY_TEST_BINARY':str(binary),'TMPDIR':str(tmp),'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1'}
record={'source_revision':revision,'shared_revision':owner['shared_revision'],'shared_source':owner['source'],'native_sha256':digest,'production_operations':False,'steps':[]}
path=root/'sqlite_backup.py';original=path.read_bytes()
code='import shared,pathlib,pytest,sys;assert str(pathlib.Path(shared.__file__).parent)==sys.argv[1];raise SystemExit(pytest.main(sys.argv[2:]))'
def test(label,target):
    xml=B/('receiving-'+label+'.xml');log=B/('receiving-'+label+'.log')
    argv=[py,'-c',code,owner['source'],target,'-q','--basetemp='+str(tmp/label),'--junitxml='+str(xml)]
    before=time.monotonic()
    with log.open('w') as output:r=subprocess.run(argv,cwd=root,env=env,stdout=output,stderr=subprocess.STDOUT)
    cases=list(ET.parse(xml).getroot().iter('testcase'))
    row={'stage':label,'argv':argv,'exit_code':r.returncode,'seconds':time.monotonic()-before,'tests':len(cases),'failures':[c.attrib['name'] for c in cases if c.find('failure') is not None],'errors':[c.attrib['name'] for c in cases if c.find('error') is not None],'skips':[c.attrib['name'] for c in cases if c.find('skipped') is not None]}
    record['steps'].append(row); print(label,row['exit_code'],row['tests'],row['failures'],flush=True)
    assert not row['errors'] and not row['skips']
    return row
row=test('sqlite-baseline','tests/test_sqlite_backup.py');assert row['exit_code']==0
for label,expression in [('sqlite-main-file','source.stat().st_size'),('sqlite-exclude-free','size - connection.execute("PRAGMA freelist_count").fetchone()[0] * connection.execute("PRAGMA page_size").fetchone()[0]')]:
    try:
        text=original.decode();assert text.count('"source_bytes": size,')==1
        # Freelist oracle query needs its own live connection, not the closed producer connection.
        if label=='sqlite-exclude-free':
            text=text.replace('        size = (','        free = connection.execute("PRAGMA freelist_count").fetchone()[0] * connection.execute("PRAGMA page_size").fetchone()[0]\n        size = (',1);expression='size - free'
        path.write_text(text.replace('"source_bytes": size,','"source_bytes": '+expression+','))
        row=test(label,'tests/test_sqlite_backup.py::test_capture_follows_only_the_collectors_sqlite_binding')
        assert row['exit_code']==1 and row['failures']==['test_capture_follows_only_the_collectors_sqlite_binding']
    finally:path.write_bytes(original);assert path.read_bytes()==original
for label,args in [('ruff-check',['check','.']),('ruff-format',['format','--check','.'])]:
    argv=[py,'-m','ruff',*args]
    with (B/('receiving-enviro-'+label+'.log')).open('w') as out:r=subprocess.run(argv,cwd=root,env=env,stdout=out,stderr=subprocess.STDOUT)
    record['steps'].append({'stage':label,'argv':argv,'exit_code':r.returncode});assert r.returncode==0
row=test('enviro-canonical','.');assert row['exit_code']==0
assert path.read_bytes()==original
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
record['status']='passed'
(B/'receiving-enviro-closure.json').write_text(json.dumps(record,indent=2)+'\n')
