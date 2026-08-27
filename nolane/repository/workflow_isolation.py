from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REF_WORKFLOW = "refoundation-epoch0-wave1.yml"
MARKER = "# REFOUNDATION_PR_ISOLATION"
GUARD = "github.event_name != 'pull_request' || !startsWith(github.head_ref, 'refoundation/')"
_JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*$")


def _strip_expression_wrapper(value: str) -> str:
    value = value.strip()
    if value.startswith("${{") and value.endswith("}}"):
        return value[3:-2].strip()
    return value


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def isolate_workflow_text(text: str) -> str:
    if "pull_request:" not in text:
        return text

    keep_newline = text.endswith("\n")
    lines = text.splitlines()
    try:
        jobs_index = next(i for i, line in enumerate(lines) if line == "jobs:")
    except StopIteration:
        return text

    headers = [i for i in range(jobs_index + 1, len(lines)) if _JOB_HEADER.match(lines[i])]
    if not headers:
        return text

    for position in range(len(headers) - 1, -1, -1):
        start = headers[position]
        end = headers[position + 1] if position + 1 < len(headers) else len(lines)
        block = "\n".join(lines[start:end])
        if "github.head_ref" in block and "refoundation/" in block:
            continue

        if_index: int | None = None
        for idx in range(start + 1, end):
            if lines[idx].startswith("    if:") and _indent_width(lines[idx]) == 4:
                if_index = idx
                break

        if if_index is None:
            insertion = [
                f"    {MARKER}",
                f"    if: ${{{{ {GUARD} }}}}",
            ]
            lines[start + 1 : start + 1] = insertion
            continue

        raw = lines[if_index].split("if:", 1)[1].strip()
        remove_end = if_index + 1
        if raw in {">", ">-", ">+", "|", "|-", "|+"}:
            expression_lines: list[str] = []
            scan = if_index + 1
            while scan < end:
                line = lines[scan]
                if line.strip() and _indent_width(line) <= 4:
                    break
                if line.strip():
                    expression_lines.append(line.strip())
                scan += 1
            existing = " ".join(expression_lines).strip()
            remove_end = scan
        else:
            existing = raw

        existing = _strip_expression_wrapper(existing)
        if not existing:
            combined = GUARD
        else:
            combined = f"({GUARD}) && ({existing})"
        replacement = [
            f"    {MARKER}",
            f"    if: ${{{{ {combined} }}}}",
        ]
        lines[if_index:remove_end] = replacement

    result = "\n".join(lines)
    if keep_newline:
        result += "\n"
    return result


def _workflow_paths(root: Path) -> tuple[Path, ...]:
    directory = root / ".github" / "workflows"
    return tuple(sorted((*directory.glob("*.yml"), *directory.glob("*.yaml"))))


def stale_workflows(root: Path = ROOT) -> tuple[str, ...]:
    stale: list[str] = []
    for path in _workflow_paths(root):
        if path.name == REF_WORKFLOW:
            continue
        text = path.read_text(encoding="utf-8")
        if isolate_workflow_text(text) != text:
            stale.append(path.relative_to(root).as_posix())
    return tuple(stale)


def write_isolation(root: Path = ROOT) -> int:
    written = 0
    for path in _workflow_paths(root):
        if path.name == REF_WORKFLOW:
            continue
        text = path.read_text(encoding="utf-8")
        isolated = isolate_workflow_text(text)
        if isolated == text:
            continue
        path.write_text(isolated, encoding="utf-8")
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Isolate historical PR workflows from refoundation/* PR heads.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    if args.write:
        count = write_isolation()
        print(f"Historical workflow isolation materialized; {count} workflow file(s) updated.")
        return 0

    stale = stale_workflows()
    if stale:
        print("Historical workflows still require Refoundation-head isolation:")
        for path in stale:
            print(f"- {path}")
        return 1
    print("Historical PR workflow isolation is fresh.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
