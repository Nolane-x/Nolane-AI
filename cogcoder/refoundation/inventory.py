from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cogcoder.organization.types import canonical_digest

from .census import CensusKind, RepositoryCensus, SourceCensusRecord
from .facades import build_active_facade_bindings
from .manifests import FIRST_GENERATION_SNAPSHOT
from .migration import LegacyDisposition, ReviewDepth


@dataclass(frozen=True, slots=True)
class GitTreeEntry:
    path: str
    mode: str
    object_type: str
    object_sha: str
    size_bytes: int | None

    def __post_init__(self) -> None:
        if not self.path or self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError("git inventory path must be normalized and repository-relative")
        if len(self.object_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in self.object_sha):
            raise ValueError("git inventory object SHA must be full 40-hex")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("git inventory object size cannot be negative")

    def to_state(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "mode": self.mode,
            "object_type": self.object_type,
            "object_sha": self.object_sha,
            "size_bytes": self.size_bytes,
        }


def _run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    return completed.stdout


def _kind_for_path(path: str) -> CensusKind:
    lower = path.lower()
    if path.startswith(".github/workflows/"):
        return CensusKind.WORKFLOW
    if path.startswith("tests/") or "/tests/" in path or Path(path).name.startswith("test_"):
        return CensusKind.TEST
    if path.startswith("docs/") or lower.endswith((".md", ".rst")):
        return CensusKind.DOCUMENTATION
    if path.startswith("model/"):
        return CensusKind.MODEL
    if path.startswith("third_party/") or path.startswith("vendor/"):
        return CensusKind.THIRD_PARTY
    if path.startswith("cogcoder/") and lower.endswith(".py"):
        name = Path(path).name
        historical_prefixes = ("r2", "_r2", "arc_")
        return CensusKind.HISTORICAL_SOURCE if name.startswith(historical_prefixes) else CensusKind.SOURCE
    if lower.endswith((".json", ".jsonl", ".lock", ".csv", ".tsv")):
        return CensusKind.RESULT
    if lower.endswith((".yml", ".yaml", ".toml", ".ini", ".cfg")):
        return CensusKind.MANIFEST
    if lower.endswith(".py"):
        return CensusKind.SOURCE
    return CensusKind.OTHER


def _module_to_path(module: str) -> str:
    return module.replace(".", "/") + ".py"


def _active_facade_destinations() -> dict[str, str]:
    return {
        _module_to_path(binding.legacy_module): _module_to_path(binding.canonical_module)
        for binding in build_active_facade_bindings()
    }


def _bootstrap_disposition(path: str) -> tuple[LegacyDisposition, ReviewDepth, str | None]:
    # Exact canonical facade binding is stronger than family mapping, but still
    # not deletion permission.  The legacy file remains live compatibility code.
    destination = _active_facade_destinations().get(path)
    if destination is not None:
        return LegacyDisposition.COMPATIBILITY, ReviewDepth.CONTRACT_REVIEWED, destination
    if path.startswith("cogcoder/organization/"):
        return LegacyDisposition.COMPATIBILITY, ReviewDepth.FAMILY_MAPPED, None
    return LegacyDisposition.KEEP, ReviewDepth.UNREVIEWED, None


@dataclass(frozen=True, slots=True)
class GitSnapshotInventory:
    source_snapshot_sha: str
    entries: tuple[GitTreeEntry, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "source_snapshot_sha": self.source_snapshot_sha,
            "entries": [row.to_state() for row in self.entries],
        }

    def __post_init__(self) -> None:
        if len(self.source_snapshot_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in self.source_snapshot_sha):
            raise ValueError("git snapshot inventory requires full source commit SHA")
        if len({row.path for row in self.entries}) != len(self.entries):
            raise ValueError("git snapshot inventory contains duplicate paths")
        if canonical_digest(self.payload()) != self.digest:
            raise ValueError("git snapshot inventory digest mismatch")

    @classmethod
    def capture(cls, repo_root: str | Path, snapshot_sha: str) -> "GitSnapshotInventory":
        root = Path(repo_root).resolve()
        resolved = _run_git(root, "rev-parse", f"{snapshot_sha}^{{commit}}").strip()
        if resolved.lower() != str(snapshot_sha).lower():
            raise ValueError(f"snapshot ref did not resolve exactly: {resolved} != {snapshot_sha}")

        raw = _run_git(root, "ls-tree", "-r", "-l", str(snapshot_sha))
        rows: list[GitTreeEntry] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                header, path = line.split("\t", 1)
                mode, object_type, object_sha, size_text = header.split(None, 3)
            except ValueError as exc:
                raise ValueError(f"non-canonical git ls-tree row: {line!r}") from exc
            size = None if size_text.strip() == "-" else int(size_text.strip())
            rows.append(
                GitTreeEntry(
                    path=path, mode=mode, object_type=object_type,
                    object_sha=object_sha, size_bytes=size,
                )
            )
        ordered = tuple(sorted(rows, key=lambda row: row.path))
        payload = {
            "source_snapshot_sha": str(snapshot_sha),
            "entries": [row.to_state() for row in ordered],
        }
        return cls(str(snapshot_sha), ordered, canonical_digest(payload))

    def to_census(self) -> RepositoryCensus:
        records: list[SourceCensusRecord] = []
        for entry in self.entries:
            disposition, review_depth, destination = _bootstrap_disposition(entry.path)
            records.append(
                SourceCensusRecord(
                    path=entry.path,
                    kind=_kind_for_path(entry.path),
                    disposition=disposition,
                    review_depth=review_depth,
                    blob_sha=entry.object_sha if entry.object_type == "blob" else None,
                    canonical_destination=destination,
                    notes=(
                        f"snapshot:{self.source_snapshot_sha}",
                        f"git_mode:{entry.mode}",
                        f"git_type:{entry.object_type}",
                    ),
                )
            )
        return RepositoryCensus(records)

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}


def write_snapshot(repo_root: str | Path, output: str | Path, snapshot_sha: str = FIRST_GENERATION_SNAPSHOT) -> Path:
    inventory = GitSnapshotInventory.capture(repo_root, snapshot_sha)
    census = inventory.to_census()
    payload = {
        "inventory": inventory.to_state(),
        "census_digest": census.digest,
        "census": [row.to_state() for row in census.records()],
        "destructive_migration_enabled": False,
    }
    target = Path(output)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate exact Nolane-AI Refoundation pinned-tree census")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--snapshot", default=FIRST_GENERATION_SNAPSHOT)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    target = write_snapshot(args.repo_root, args.output, args.snapshot)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
