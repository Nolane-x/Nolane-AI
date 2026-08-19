from __future__ import annotations

from pathlib import Path

path = Path("cogcoder/r269_transfer_runtime.py")
text = path.read_text(encoding="utf-8")
old = '''            if eliminated_priors:
                contradictions += len(eliminated_priors)
                quarantine = True
            if not transfer and before_priors:
                abandoned = True
'''
new = '''            if eliminated_priors:
                quarantine = True
            if not transfer and before_priors:
                contradictions += 1
                abandoned = True
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one multi-prior contradiction boundary, found {text.count(old)}")
text = text.replace(old, new)
compile(text, str(path), "exec")
path.write_text(text, encoding="utf-8")
