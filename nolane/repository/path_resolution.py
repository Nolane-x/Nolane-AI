from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _normalized_relative_path(path: str | Path) -> str:
    text = Path(path).as_posix()
    while text.startswith("./"):
        text = text[2:]
    candidate = Path(text)
    if not text or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"repository path must be a safe relative path: {path!r}")
    return candidate.as_posix()


def resolve_repository_path(path: str | Path, *, root: Path = ROOT) -> str:
    """Resolve a repository-relative path across the zero-loss history migration.

    Active paths are returned unchanged. If a historical root artifact was moved by
    Refoundation, its canonical archive location is resolved through archive/INDEX.json.
    The ledger entry and archived bytes are verified before the migrated path is returned.
    Missing, ambiguous, or corrupted provenance fails closed.
    """

    relative = _normalized_relative_path(path)
    root = root.resolve()
    direct = root / relative
    if direct.is_file():
        return relative

    index_path = root / "archive" / "INDEX.json"
    if not index_path.is_file():
        raise FileNotFoundError(f"repository path not found and archive ledger is absent: {relative}")

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    matches = [row for row in payload.get("entries", ()) if row.get("original_path") == relative]
    if not matches:
        raise FileNotFoundError(f"repository path is neither active nor archived: {relative}")
    if len(matches) != 1:
        raise RuntimeError(f"archive ledger contains ambiguous provenance for: {relative}")

    row = matches[0]
    if row.get("move_status") != "moved" or row.get("delete_allowed") is not False:
        raise RuntimeError(f"archive ledger entry is not a zero-loss moved artifact: {relative}")

    target_text = _normalized_relative_path(str(row.get("archive_target", "")))
    target = root / target_text
    if not target.is_file():
        raise FileNotFoundError(f"archive ledger target is missing: {target_text}")

    expected_sha256 = row.get("sha256")
    actual_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    if not isinstance(expected_sha256, str) or actual_sha256 != expected_sha256:
        raise RuntimeError(f"archive ledger checksum mismatch for: {relative}")

    return target_text
