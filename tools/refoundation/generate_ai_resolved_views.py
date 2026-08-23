from __future__ import annotations

import json
from pathlib import Path

from nolane.ai.catalog import ROOT, load_profiles
from nolane.ai.resolver import render_resolved_markdown, resolve_ai


def generate() -> tuple[Path, ...]:
    written: list[Path] = []
    for profile in load_profiles():
        folder = ROOT / "ai" / profile.agent_id
        folder.mkdir(parents=True, exist_ok=True)
        resolved = resolve_ai(profile.agent_id)
        json_path = folder / "RESOLVED.json"
        md_path = folder / "RESOLVED.md"
        json_path.write_text(json.dumps(resolved.to_state(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md_path.write_text(render_resolved_markdown(resolved), encoding="utf-8")
        written.extend((json_path, md_path))
    return tuple(written)


if __name__ == "__main__":
    paths = generate()
    print(f"generated {len(paths)} resolved AI view files")
