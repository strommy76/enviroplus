# Method, inputs and limits
November1,2026. Enviroplus source8eea5664f196bc91b97dadf92e33af5643864f34, shared
5cafbba3c19a7d52901083dcd0b8b26635e178be. Canonical agent-config/AGENTS.md and
OPERATOR.md read in this turn; plan carries original authority and C/H boundary.
No production/test source changed. Pending calibration docs PR25 changes no test
or runtime source bytes.

Used the existing deployed pimoroni interpreter, pytest/Ruff/rclone. No installs.
Every existing test receives a throwaway ENVIRO_RAW_ROOT through tests/conftest.py.
Fixture .env/config/database files are synthetic scratch under this effort, never
production .env or the canonical raw tree. Operator photos, SQLite observations,
retained payloads and credentials are excluded from public audit/review snapshots.

Executed in the audit worktree with PYTHONDONTWRITEBYTECODE=1 and
PYTHONPATH=/home/pistrommy/projects:
```sh
/home/pistrommy/.virtualenvs/pimoroni/bin/python -m pytest --collect-only -q tests \
  -o cache_dir=<effort>/pytest-cache
/home/pistrommy/.virtualenvs/pimoroni/bin/python -m pytest -q \
  --basetemp=<effort>/pytest-tmp -o cache_dir=<effort>/pytest-cache
/home/pistrommy/.virtualenvs/pimoroni/bin/python -m ruff check .
/home/pistrommy/.virtualenvs/pimoroni/bin/python -m ruff format --check .
```
Collection:273 cases in0.42s; execution273 passed in5.62s; Ruff/format pass.
`collected-cases.txt` contains exact observed node IDs without pytest summary.
AST enumerated test_ functions/source lines. Author read all tests/fixtures and
relevant production owners/config, then gave explicit per-function judgments.
Joined to actual IDs before the first `[`, with a per-case override for the five
all-absent pages. Set equality and uniqueness checked179 functions/273 cases.
Judgment output is cases.csv; the one-use author worksheet is kept in the effort,
not installed as a lasting validator. Reproduce inventory identity checks:
```python
import ast, csv
from pathlib import Path
rows = list(csv.DictReader(Path('docs/test-suite-audit/cases.csv').open()))
ids = Path('docs/test-suite-audit/collected-cases.txt').read_text().splitlines()
assert [r['case_id'] for r in rows] == ids
assert len(set(ids)) == len(ids)
locations = {str(p) + '::' + n.name: n.lineno
             for p in Path('tests').glob('test_*.py')
             for n in ast.walk(ast.parse(p.read_text()))
             if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')}
assert set(locations) == {i.split('[', 1)[0] for i in ids}
assert all(int(r['test_line_at_8eea566']) == locations[r['case_id'].split('[', 1)[0]]
           for r in rows)
```

Initial collect-only was mistakenly invoked in parent projects:26 import/collection
errors,734 partial cases, no test execution. Excluded from Enviroplus inventory;
raw failed discovery remains private in this effort. The explicit-worktree/tests
command above corrected the invocation; no app assertions were bent to pass it.
A report-writing attempt used an incorrect relative base path and failed before
writing; the explicit effort-root worksheet corrected it. These are author
invocation errors, not product/test defects.

Current-practice check: official pytest generated case IDs and boundary mocking,
plus Cosmic Ray's definition of actual-source mutation. Links and divergence from
a mutation campaign are in plan.md. No threshold or necessity judgment is inferred
from external guidance alone. All recommendations are finite source analysis.
