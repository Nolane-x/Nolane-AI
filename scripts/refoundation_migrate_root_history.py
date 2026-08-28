from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
INDEX = ROOT / "archive" / "INDEX.json"

_SCAN_PRUNE_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "archive",
    "node_modules",
}
_REWRITE_EXCLUDE = {
    ".github/workflows/refoundation-wave5as-repository-surface-carrier.yml",
    "nolane/repository/audit.py",
    "nolane/repository/audit_v2.py",
    "scripts/refoundation_debug_root_history_refs.py",
    "scripts/refoundation_migrate_root_history.py",
    "tests/test_refoundation_git_inventory.py",
    "tests/test_refoundation_wave4_repository_quarantine.py",
    "tests/test_refoundation_wave5as_repository_surface.py",
}
_MAX_TEXT_BYTES = 5 * 1024 * 1024
_QUOTED_TOKEN = re.compile(r"(?P<q>['\"`])(?P<token>[^'\"`\n]+)(?P=q)")
_GLOB_META = frozenset("*?[")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_index() -> dict:
    payload = json.loads(INDEX.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    if not entries:
        raise RuntimeError("archive/INDEX.json contains no historical entries")
    return payload


def _verify_source_receipts(entries: list[dict]) -> None:
    seen: set[str] = set()
    for row in entries:
        name = row["original_path"]
        if name in seen:
            raise RuntimeError(f"duplicate historical receipt: {name}")
        seen.add(name)
        source = ROOT / name
        target = ROOT / row["archive_target"]
        expected = row["sha256"]
        if source.is_file():
            actual = _sha256(source)
        elif target.is_file():
            actual = _sha256(target)
        else:
            raise RuntimeError(f"historical artifact missing from root and archive: {name}")
        if actual != expected:
            raise RuntimeError(f"historical artifact digest drift before move: {name}: {actual}")


def _move_artifacts(entries: list[dict]) -> int:
    moved = 0
    for row in entries:
        source = ROOT / row["original_path"]
        target = ROOT / row["archive_target"]
        expected = row["sha256"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            if target.exists():
                raise RuntimeError(f"archive target already exists while root source remains: {target}")
            shutil.move(str(source), str(target))
            moved += 1
        if not target.is_file():
            raise RuntimeError(f"archive target missing after move: {target}")
        actual = _sha256(target)
        if actual != expected:
            raise RuntimeError(
                f"byte preservation failure for {row['original_path']}: expected {expected}, got {actual}"
            )
    return moved


def _iter_rewrite_text():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(name for name in dirnames if name not in _SCAN_PRUNE_DIRS)
        base = Path(dirpath)
        for filename in sorted(filenames):
            path = base / filename
            relative = path.relative_to(ROOT)
            if relative.as_posix() in _REWRITE_EXCLUDE:
                continue
            try:
                if path.stat().st_size > _MAX_TEXT_BYTES:
                    continue
                raw = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in raw:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            yield path, text


def _archive_pattern_for_root_token(token: str) -> str | None:
    """Return the archive-qualified form only for a real root filename/glob token."""
    if not token or "/" in token or "\\" in token:
        return None
    if any(ch.isspace() for ch in token):
        return None
    if not any(ch in token for ch in _GLOB_META):
        return None
    if token.startswith("CURRENT_ONE_WEIGHT_"):
        return f"archive/root-history/legacy_weight_pointer/{token}"
    if token.startswith("R["):
        return f"archive/root-history/historical_r_series/{token}"
    if len(token) > 1 and token[0] == "R" and token[1].isdigit():
        return f"archive/root-history/historical_r_series/{token}"
    return None


def _prefix_quoted_globs(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        q = match.group("q")
        token = match.group("token")
        archived = _archive_pattern_for_root_token(token)
        if archived is None:
            return match.group(0)
        return f"{q}{archived}{q}"

    return _QUOTED_TOKEN.sub(replace, text)


def _rewrite_references(entries: list[dict]) -> int:
    pairs = [(row["original_path"], row["archive_target"]) for row in entries]
    changed = 0
    for path, original in _iter_rewrite_text():
        text = original
        for index, (name, target) in enumerate(pairs):
            placeholder = f"__NOLANE_ARCHIVE_TARGET_{index:04d}__"
            text = text.replace(f"./{target}", placeholder)
            text = text.replace(target, placeholder)
            text = text.replace(name, target)
            text = text.replace(placeholder, target)
        text = _prefix_quoted_globs(text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def _append_once(path: Path, marker: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + block.strip() + "\n", encoding="utf-8")


def _record_closure() -> None:
    _append_once(
        ROOT / "CURRENT" / "STATUS.md",
        "## Wave 5AS — repository surface closure",
        """
## Wave 5AS — repository surface closure

Wave 5AS completes the physical repository-surface refoundation. Every historical root artifact tracked by the repository-history ledger is byte-preservingly relocated to its canonical `archive/root-history/<category>/...` target, all active references are rewritten to archive-qualified paths, and the root no longer exposes R-series delivery/release/recovery/readiness/evidence files, legacy current-weight pointers, the legacy root status document, or the historical checkpoint pointer. Historical artifacts remain immutable provenance with `delete_allowed=false`.

The repository audit now understands both quarantined and moved history and treats archive-qualified references as valid provenance instead of bare-root dependency debt. `archive/INDEX.json` remains the generated ledger and records each relocated artifact as `move_status=moved` only when its archive target exists with the original SHA-256 and no bare-root reference blockers remain. The R2.2 integrity workflow is retained for historical/manual verification but is no longer an automatic `main` gate because its source-drift contract intentionally describes the frozen R2.2 release rather than current A1 implementation authority.
""",
    )
    _append_once(
        ROOT / "CURRENT" / "REPOSITORY_AUTHORITY.md",
        "## Repository surface closure",
        """
## Repository surface closure

Wave 5AS converts the Wave-4 quarantine plan into a physical repository boundary. Historical root artifacts are expected to live under `archive/root-history/` after verified relocation. A `moved` receipt means the archive target exists byte-for-byte at the recorded SHA-256 and the active repository contains no bare reference that still requires the former root path. `quarantined_in_place` remains valid only for a newly discovered or not-yet-migrated historical artifact.

Historical release integrity workflows do not outrank current architecture authority. A frozen release verifier whose contract hashes historical source must be scoped to its historical/manual verification context rather than automatically treating later `main` evolution as release corruption.
""",
    )


def _materialize_and_verify(entries: list[dict]) -> None:
    from nolane.repository.audit import build_archive_index, write_materialized_audit

    write_materialized_audit(source_root=ROOT, output_root=ROOT)
    payload = build_archive_index(ROOT)
    actual = {row["original_path"]: row for row in payload["entries"]}
    expected_names = {row["original_path"] for row in entries}
    if set(actual) != expected_names:
        raise RuntimeError(
            f"archive ledger coverage changed during move: missing={sorted(expected_names - set(actual))}, "
            f"extra={sorted(set(actual) - expected_names)}"
        )
    for old in entries:
        row = actual[old["original_path"]]
        if row["move_status"] != "moved":
            raise RuntimeError(f"artifact did not close as moved: {old['original_path']}")
        if row["sha256"] != old["sha256"]:
            raise RuntimeError(f"archive receipt digest changed: {old['original_path']}")
        if row["reference_audit"]["blockers"]:
            raise RuntimeError(
                f"reference blockers remain for {old['original_path']}: {row['reference_audit']['blockers']}"
            )


def apply() -> dict[str, int]:
    payload = _load_index()
    entries = list(payload["entries"])
    _verify_source_receipts(entries)
    moved = _move_artifacts(entries)
    rewritten = _rewrite_references(entries)
    _record_closure()
    _materialize_and_verify(entries)
    return {"artifacts": len(entries), "moved": moved, "rewritten_files": rewritten}


def check() -> dict[str, int]:
    payload = _load_index()
    entries = list(payload["entries"])
    root_left = [row["original_path"] for row in entries if (ROOT / row["original_path"]).exists()]
    if root_left:
        raise RuntimeError(f"historical artifacts still exposed at repository root: {root_left}")
    for row in entries:
        target = ROOT / row["archive_target"]
        if not target.is_file():
            raise RuntimeError(f"archive target missing: {row['archive_target']}")
        if _sha256(target) != row["sha256"]:
            raise RuntimeError(f"archive target digest mismatch: {row['archive_target']}")
        if row["move_status"] != "moved":
            raise RuntimeError(f"archive index is not closed as moved: {row['original_path']}")
        if row["reference_audit"]["blockers"]:
            raise RuntimeError(
                f"archive index retains root-reference blockers: {row['original_path']}: "
                f"{row['reference_audit']['blockers']}"
            )
    return {"artifacts": len(entries), "root_left": 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relocate Nolane historical root artifacts without losing provenance.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    result = apply() if args.apply else check()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
