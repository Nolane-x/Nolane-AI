from __future__ import annotations

import argparse
import json
from pathlib import Path

from nolane.core.canonical_digest import canonical_digest

from .manifests import FIRST_GENERATION_SNAPSHOT, build_bootstrap_agent_manifests


def write_agent_manifest_set(output_root: str | Path) -> Path:
    root = Path(output_root)
    agents_dir = root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    index_rows: list[dict[str, str]] = []
    manifests = build_bootstrap_agent_manifests()
    for row in manifests:
        state = row.to_state()
        digest = canonical_digest(state)
        target = agents_dir / f"{row.agent_id}.json"
        target.write_text(
            json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        index_rows.append(
            {
                "agent_id": row.agent_id,
                "path": f"agents/{target.name}",
                "agent_definition_version": row.agent_definition_version,
                "neural_version": row.neural_version,
                "digest": digest,
            }
        )

    payload = {
        "source_snapshot_sha": FIRST_GENERATION_SNAPSHOT,
        "permanent_identity_count": len(manifests),
        "manifests": sorted(index_rows, key=lambda item: item["agent_id"]),
    }
    index = {**payload, "index_digest": canonical_digest(payload)}
    index_path = root / "agents.index.json"
    index_path.write_text(
        json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return index_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Refoundation Epoch-0 permanent agent manifests")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    index = write_agent_manifest_set(args.output_dir)
    print(index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
