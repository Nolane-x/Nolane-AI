from __future__ import annotations

import argparse
import json
from pathlib import Path

from nolane.metadata.version_discipline import check_git_revision_discipline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m nolane.metadata.version_discipline_cli",
        description="Read-only component-local version discipline gate.",
    )
    parser.add_argument("--base", required=True, help="exact Git base ref")
    parser.add_argument("--head", required=True, help="exact Git head ref")
    parser.add_argument("--repo-root", default=".", help="repository working tree")
    parser.add_argument("--check", action="store_true", help="exit nonzero on findings")
    parser.add_argument("--json", action="store_true", help="emit deterministic JSON")
    args = parser.parse_args(argv)

    report = check_git_revision_discipline(Path(args.repo_root), args.base, args.head)
    if args.json:
        print(json.dumps(report.to_state(), sort_keys=True, separators=(",", ":")))
    else:
        status = "PASS" if report.clean else "FAIL"
        print(f"Component-local version discipline: {status} ({len(report.findings)} finding(s))")
        for finding in report.findings:
            print(f"- {finding.code.value}: {finding.component_id}: {finding.detail}")
    if args.check and not report.clean:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("main",)
