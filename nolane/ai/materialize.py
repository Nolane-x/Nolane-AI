from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .catalog import ROOT, load_profiles
from .resolver import render_resolved_markdown, resolve_ai


def rendered_files(root: Path = ROOT) -> dict[Path, str]:
    """Return every deterministic derived dossier without mutating the tree."""
    outputs: dict[Path, str] = {}
    for profile in load_profiles():
        row = resolve_ai(profile.agent_id)
        folder = root / "ai" / profile.agent_id
        outputs[folder / "RESOLVED.json"] = (
            json.dumps(row.to_state(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )
        outputs[folder / "RESOLVED.md"] = render_resolved_markdown(row)
    if len(outputs) != 134:
        raise ValueError(f"expected exactly 134 derived dossier files, got {len(outputs)}")
    return outputs


def stale_paths(root: Path = ROOT) -> tuple[Path, ...]:
    stale: list[Path] = []
    for path, expected in rendered_files(root).items():
        try:
            actual = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            stale.append(path)
            continue
        if actual != expected:
            stale.append(path)
    return tuple(stale)


def write_materialized(root: Path = ROOT) -> tuple[Path, ...]:
    written: list[Path] = []
    for path, content in rendered_files(root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)
    return tuple(written)


def _display(paths: Iterable[Path], root: Path) -> str:
    return "\n".join(str(path.relative_to(root)) for path in paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize or verify the 67 canonical Nolane AI resolved dossiers."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if any RESOLVED view is missing or stale")
    mode.add_argument("--write", action="store_true", help="write missing or stale RESOLVED views")
    args = parser.parse_args(argv)

    if args.check:
        stale = stale_paths(ROOT)
        if stale:
            print(_display(stale, ROOT))
            return 1
        print("67/67 AI dossiers are fresh (134 derived files).")
        return 0

    written = write_materialized(ROOT)
    if written:
        print(_display(written, ROOT))
    print(f"materialized {len(written)} changed file(s); 67/67 AI dossiers resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
