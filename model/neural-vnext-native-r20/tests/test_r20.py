from __future__ import annotations
import json
from pathlib import Path
def test_fresh_locked():
    root=Path(__file__).resolve().parents[1]
    x=json.loads((root/"PREDEV_LOCK.json").read_text())
    assert x["fresh_isolation"]["status"]=="UNOPENED"
    assert x["benchmark"]["fresh_indices"]==[280,319]
