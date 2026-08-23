from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compatibility import build_bootstrap_parity_report
from .composition import build_wave1_composition_lock
from .facades import build_active_facade_bindings, validate_active_facades
from .manifests import (
    FIRST_GENERATION_SNAPSHOT,
    REFUNDATION_EPOCH,
    build_bootstrap_agent_manifests,
    build_component_manifests,
)


def build_bootstrap_report() -> dict[str, object]:
    parity = build_bootstrap_parity_report()
    facade_parity = validate_active_facades()
    facades = build_active_facade_bindings()
    lock = build_wave1_composition_lock()
    agents = build_bootstrap_agent_manifests()
    components = build_component_manifests()
    rank_counts: dict[str, int] = {}
    for row in agents:
        rank_counts[row.rank] = rank_counts.get(row.rank, 0) + 1
    return {
        "refoundation_epoch": REFUNDATION_EPOCH,
        "canonical_bootstrap_version": "0.0.0",
        "source_snapshot_sha": FIRST_GENERATION_SNAPSHOT,
        "destructive_migration_enabled": False,
        "identity_summary": {
            "count": len(agents),
            "rank_counts": dict(sorted(rank_counts.items())),
            "bootstrap_parity_clean": parity.clean,
            "bootstrap_parity_digest": parity.digest,
        },
        "active_facade_summary": {
            "count": len(facades),
            "clean": facade_parity.clean,
            "parity_digest": facade_parity.digest,
        },
        "agents": [row.to_state() for row in agents],
        "components": [row.to_state() for row in components],
        "active_facades": [row.to_state() for row in facades],
        "composition_lock": lock.to_state(),
        "bootstrap_parity": {
            **parity.payload(),
            "clean": parity.clean,
            "digest": parity.digest,
        },
        "active_facade_parity": {
            **facade_parity.payload(),
            "clean": facade_parity.clean,
            "digest": facade_parity.digest,
        },
    }


def write_bootstrap_report(output: str | Path) -> Path:
    target = Path(output)
    target.write_text(
        json.dumps(build_bootstrap_report(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Refoundation Epoch-0 bootstrap manifests and parity evidence")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    target = write_bootstrap_report(args.output)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
