from __future__ import annotations

import runpy
from pathlib import Path


runpy.run_path('.github/e_acting_workspace_fencing_patch.py', run_name='__main__')

path = Path('tests/test_refoundation_acting_workspace_fencing.py')
source = path.read_text(encoding='utf-8')
old = '''            "workspace_provenance_version": 2,\n            "initial_workspace_digest": "workspace-initial",\n            "current_workspace_digest": "workspace-current",\n        }\n    )\n    session = ExecutionSession.from_state(state)\n    plane = _plane(session=session)\n'''
new = '''            "workspace_provenance_version": 2,\n            "initial_workspace_digest": "workspace-current",\n            "current_workspace_digest": "workspace-current",\n        }\n    )\n    session = ExecutionSession.from_state(state)\n    plane = _plane(session=session)\n'''
if source.count(old) != 1:
    raise SystemExit('expected unique empty-session provenance test anchor')
source = source.replace(old, new, 1)
old_assertions = '''    assert roundtrip["workspace_provenance_version"] == 2\n    assert roundtrip["initial_workspace_digest"] == "workspace-initial"\n    assert roundtrip["current_workspace_digest"] == "workspace-current"\n'''
new_assertions = '''    assert roundtrip["workspace_provenance_version"] == 2\n    assert roundtrip["initial_workspace_digest"] == "workspace-current"\n    assert roundtrip["current_workspace_digest"] == "workspace-current"\n'''
if source.count(old_assertions) != 1:
    raise SystemExit('expected unique empty-session roundtrip assertion anchor')
path.write_text(source.replace(old_assertions, new_assertions, 1), encoding='utf-8')
