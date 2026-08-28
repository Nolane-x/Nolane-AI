from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


ROOT = Path(__file__).resolve().parents[2]
COMPONENT_VERSION = "0.0.0"
ARCHIVE_SCHEMA_VERSION = "nolane-repository-history-v1"
DEBT_SCHEMA_VERSION = "nolane-native-debt-v1"
REFERENCE_AUDIT_POLICY = "root-reference-aware-zero-loss-v2"

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
_REFERENCE_SCAN_EXCLUDE = {
    ".github/workflows/refoundation-wave5as-repository-surface-carrier.yml",
    "nolane/repository/audit.py",
    "nolane/repository/audit_v2.py",
    "scripts/refoundation_debug_root_history_refs.py",
    "scripts/refoundation_migrate_root_history.py",
    "tests/test_refoundation_git_inventory.py",
    "tests/test_refoundation_wave4_repository_quarantine.py",
    "tests/test_refoundation_wave5as_repository_surface.py",
}
_MAX_REFERENCE_SCAN_BYTES = 5 * 1024 * 1024
_QUOTED_TOKEN = re.compile(r"(?P<q>['\"`])(?P<token>[^'\"`\n]+)(?P=q)")
_GLOB_META = frozenset("*?[")


def _is_historical_name(name: str) -> bool:
    return bool(
        (name.startswith("R") and len(name) > 1 and name[1].isdigit())
        or name.startswith("CURRENT_ONE_WEIGHT_")
        or name == "CURRENT_STATUS.md"
        or name == "CHECKPOINT_MANIFEST.json"
    )


def _root_dynamic_category_for_token(token: str) -> str | None:
    """Classify an actual quoted root filename/glob, never prose or a path."""
    if not token or "/" in token or "\\" in token:
        return None
    if any(ch.isspace() for ch in token):
        return None
    if not any(ch in token for ch in _GLOB_META):
        return None
    if token.startswith("CURRENT_ONE_WEIGHT_"):
        return "legacy_weight_pointer"
    if token.startswith("R["):
        return "historical_r_series"
    if len(token) > 1 and token[0] == "R" and token[1].isdigit():
        return "historical_r_series"
    return None


def _root_dynamic_categories(line: str) -> set[str]:
    categories: set[str] = set()
    for match in _QUOTED_TOKEN.finditer(line):
        category = _root_dynamic_category_for_token(match.group("token"))
        if category is not None:
            categories.add(category)
    return categories


def _historical_root_candidates(root: Path) -> tuple[Path, ...]:
    rows = [path for path in root.iterdir() if path.is_file() and _is_historical_name(path.name)]
    return tuple(sorted(rows, key=lambda p: p.name))


def _archived_history_candidates(root: Path) -> tuple[Path, ...]:
    base = root / "archive" / "root-history"
    if not base.is_dir():
        return ()
    rows = [
        path
        for path in base.rglob("*")
        if path.is_file() and _is_historical_name(path.name)
    ]
    return tuple(sorted(rows, key=lambda p: (p.name, p.as_posix())))


def _classification(name: str) -> tuple[str, str]:
    if name.startswith("CURRENT_ONE_WEIGHT_"):
        return (
            "legacy_weight_pointer",
            "Legacy current-weight pointer retained for checkpoint/release provenance; it is not current architecture law.",
        )
    if name == "CURRENT_STATUS.md":
        return (
            "legacy_current_status",
            "Legacy root status document superseded architecturally by CURRENT/STATUS.md.",
        )
    if name == "CHECKPOINT_MANIFEST.json":
        return (
            "historical_checkpoint_pointer",
            "Historical checkpoint manifest retained for model/release provenance; checkpoint evidence is governed separately from CURRENT architecture law.",
        )
    return (
        "historical_r_series",
        "Historical R-series research, delivery, release, recovery, readiness, or evidence material retained for scientific provenance.",
    )


def _expected_archive_target(name: str) -> str:
    category, _ = _classification(name)
    return f"archive/root-history/{category}/{name}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_kind(relative: Path) -> str:
    parts = relative.parts
    if len(parts) >= 3 and parts[0] == ".github" and parts[1] == "workflows":
        return "workflow"
    if parts and parts[0] == "tests":
        return "test"
    if parts and parts[0] in {"cogcoder", "nolane"}:
        return "active_source"
    if parts and parts[0] in {"scripts", "tools"}:
        return "script"
    if relative.suffix.lower() in {".sh", ".bash", ".ps1", ".bat", ".cmd"}:
        return "script"
    if (parts and parts[0] == "docs") or relative.suffix.lower() in {".md", ".rst"}:
        return "documentation"
    return "repository_metadata"


def _iter_reference_text(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in _SCAN_PRUNE_DIRS)
        base = Path(dirpath)
        for filename in sorted(filenames):
            path = base / filename
            relative = path.relative_to(root)
            if relative.as_posix() in _REFERENCE_SCAN_EXCLUDE:
                continue
            if len(relative.parts) == 1 and _is_historical_name(relative.name):
                continue
            try:
                if path.stat().st_size > _MAX_REFERENCE_SCAN_BYTES:
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
            yield relative, text


def _strip_archive_qualified_references(line: str, targets: tuple[str, ...]) -> str:
    cleaned = line
    for target in targets:
        cleaned = cleaned.replace(f"./{target}", "")
        cleaned = cleaned.replace(target, "")
    return cleaned


def _history_locations(root: Path) -> dict[str, tuple[Path, str]]:
    rows: dict[str, tuple[Path, str]] = {}
    for path in _historical_root_candidates(root):
        rows[path.name] = (path, "quarantined_in_place")
    for path in _archived_history_candidates(root):
        expected = root / _expected_archive_target(path.name)
        if path.resolve() != expected.resolve():
            raise RuntimeError(
                f"historical artifact outside canonical archive target: {path.relative_to(root).as_posix()}"
            )
        if path.name in rows:
            raise RuntimeError(f"historical artifact exists at root and archive simultaneously: {path.name}")
        rows[path.name] = (path, "moved")
    return dict(sorted(rows.items()))


def _build_reference_audits(
    root: Path,
    locations: Mapping[str, tuple[Path, str]],
) -> dict[str, dict[str, Any]]:
    names = tuple(sorted(locations))
    exact: dict[str, list[dict[str, Any]]] = {name: [] for name in names}
    dynamic_categories: set[str] = set()
    targets = tuple(_expected_archive_target(name) for name in names)

    for relative, text in _iter_reference_text(root):
        kind = _reference_kind(relative)
        for line_number, line in enumerate(text.splitlines(), start=1):
            cleaned = _strip_archive_qualified_references(line, targets)
            for name in names:
                if name in cleaned:
                    exact[name].append(
                        {
                            "path": relative.as_posix(),
                            "line": line_number,
                            "kind": kind,
                        }
                    )
            if "archive/root-history/" not in cleaned:
                dynamic_categories.update(_root_dynamic_categories(cleaned))

    audits: dict[str, dict[str, Any]] = {}
    for name, (_, move_status) in locations.items():
        category, _ = _classification(name)
        references = sorted(
            exact[name],
            key=lambda row: (row["path"], row["line"], row["kind"]),
        )
        blockers: set[str] = set()
        if references:
            blockers.add("bare_root_reference_present")
        if category in dynamic_categories:
            blockers.add("root_dynamic_reference_present")

        if move_status == "quarantined_in_place":
            if category in {"historical_checkpoint_pointer", "legacy_weight_pointer"}:
                blockers.add("protected_provenance_pointer")
            blockers.add("migration_receipt_missing")
            decision = "quarantined_in_place"
        else:
            decision = "moved" if not blockers else "moved_with_reference_debt"

        audits[name] = {
            "decision": decision,
            "reference_count": len(references),
            "references": references,
            "blockers": sorted(blockers),
        }
    return audits


def build_archive_index(root: Path = ROOT) -> dict[str, Any]:
    locations = _history_locations(root)
    reference_audits = _build_reference_audits(root, locations)
    entries: list[dict[str, Any]] = []
    for name, (path, move_status) in locations.items():
        category, reason = _classification(name)
        target = _expected_archive_target(name)
        entries.append(
            {
                "original_path": name,
                "category": category,
                "authority": "historical",
                "sha256": _sha256(path),
                "archive_target": target,
                "move_status": move_status,
                "delete_allowed": False,
                "reason": reason,
                "reference_audit": reference_audits[name],
            }
        )
    return {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "component_version": COMPONENT_VERSION,
        "policy": "fail_closed_zero_loss",
        "reference_audit_policy": REFERENCE_AUDIT_POLICY,
        "entries": entries,
    }


def build_native_debt() -> dict[str, Any]:
    ledger = build_component_implementation_ledger()
    components: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for component_id in sorted(ledger):
        row = ledger[component_id]
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        status = row.status.value
        counts[status] = counts.get(status, 0) + 1
        components.append(
            {
                "component_id": row.component_id,
                "component_version": row.component_version,
                "implementation_status": status,
                "canonical_module": row.canonical_module,
                "legacy_sources": list(row.legacy_sources),
                "canonical_write_authority": row.canonical_write_authority,
                "notes": row.notes,
            }
        )
    return {
        "schema_version": DEBT_SCHEMA_VERSION,
        "repository_quarantine_version": COMPONENT_VERSION,
        "definition": "Every canonical component not yet classified canonical_native. This is migration debt, not a capability-failure claim.",
        "counts_by_status": {key: counts[key] for key in sorted(counts)},
        "components": components,
    }


def render_native_debt_markdown(payload: Mapping[str, Any]) -> str:
    components = list(payload["components"])
    counts = dict(payload["counts_by_status"])
    lines = [
        "# Native Implementation Debt",
        "",
        f"Repository quarantine component: `{payload['repository_quarantine_version']}`.",
        "",
        "This file is a generated human-readable view of `CURRENT/NATIVE_DEBT.json`. It lists every canonical semantic component whose executable implementation is not yet classified `canonical_native`. It does **not** mean the component is broken or unaccepted; it makes remaining migration work impossible to hide.",
        "",
        "## Counts",
        "",
    ]
    if counts:
        for status in sorted(counts):
            lines.append(f"- `{status}`: {counts[status]}")
    else:
        lines.append("- No remaining non-native components.")
    lines.extend(("", "## Components", ""))
    for row in components:
        canonical = row["canonical_module"] or "none"
        legacy = ", ".join(row["legacy_sources"]) or "none declared"
        lines.extend(
            (
                f"### `{row['component_id']}`",
                "",
                f"- Component version: `{row['component_version']}`",
                f"- Status: `{row['implementation_status']}`",
                f"- Canonical module: `{canonical}`",
                f"- Canonical write authority: `{str(bool(row['canonical_write_authority'])).lower()}`",
                f"- Legacy/provenance sources: {legacy}",
                f"- Notes: {row['notes']}",
                "",
            )
        )
    lines.append(
        "> GENERATED VIEW — update implementation authority at its canonical source and regenerate; never hand-edit this debt projection."
    )
    lines.append("")
    return "\n".join(lines)


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _expected_materialization(source_root: Path) -> dict[Path, bytes]:
    debt = build_native_debt()
    return {
        Path("archive/INDEX.json"): _json_bytes(build_archive_index(source_root)),
        Path("CURRENT/NATIVE_DEBT.json"): _json_bytes(debt),
        Path("CURRENT/NATIVE_DEBT.md"): render_native_debt_markdown(debt).encode("utf-8"),
    }


def stale_paths(*, source_root: Path = ROOT, output_root: Path = ROOT) -> tuple[str, ...]:
    stale: list[str] = []
    for relative, expected in _expected_materialization(source_root).items():
        target = output_root / relative
        try:
            actual = target.read_bytes()
        except FileNotFoundError:
            stale.append(relative.as_posix())
            continue
        if actual != expected:
            stale.append(relative.as_posix())
    return tuple(stale)


def write_materialized_audit(*, source_root: Path = ROOT, output_root: Path = ROOT) -> int:
    written = 0
    for relative, expected in _expected_materialization(source_root).items():
        target = output_root / relative
        if target.is_file() and target.read_bytes() == expected:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected)
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize/check Nolane repository history and native-debt audit views."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Write deterministic audit projections.")
    mode.add_argument("--check", action="store_true", help="Fail if committed audit projections are stale or missing.")
    args = parser.parse_args(argv)

    if args.write:
        count = write_materialized_audit()
        print(f"Repository audit materialized; {count} file(s) updated.")
        return 0

    stale = stale_paths()
    if stale:
        print("Repository audit projections are stale or missing:")
        for path in stale:
            print(f"- {path}")
        return 1

    archive = build_archive_index()
    debt = build_native_debt()
    moved = sum(1 for row in archive["entries"] if row["move_status"] == "moved")
    quarantined = len(archive["entries"]) - moved
    reference_debt = sum(1 for row in archive["entries"] if row["reference_audit"]["blockers"])
    print(
        f"Repository audit fresh: {len(archive['entries'])} historical artifacts; "
        f"{moved} moved / {quarantined} quarantined; "
        f"{reference_debt} with reference debt; "
        f"{len(debt['components'])} non-native component records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
