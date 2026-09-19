from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping

HERE = Path(__file__).resolve()
VNEXT_ROOT = HERE.parents[1]
if str(VNEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(VNEXT_ROOT))

from nvnext.gate import evaluate_frozen_fresh_gate  # noqa: E402
from nvnext.pipeline import load_predev_lock, sha256_file, sha256_json_file  # noqa: E402


def _read_rows(path: Path) -> list[Mapping[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("rows")
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array or an object with rows")
    if not all(isinstance(row, dict) for row in payload):
        raise ValueError(f"{path} rows must be JSON objects")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the preregistered Neural vNext 160-episode frozen neural-only gate."
    )
    parser.add_argument("--candidate-bundle", required=True, type=Path)
    parser.add_argument("--candidate-manifest", required=True, type=Path)
    parser.add_argument("--parent-results", required=True, type=Path)
    parser.add_argument("--candidate-results", required=True, type=Path)
    parser.add_argument(
        "--predev-lock",
        type=Path,
        default=VNEXT_ROOT / "PREDEV_LOCK.json",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    lock = load_predev_lock(args.predev_lock)
    manifest = json.loads(args.candidate_manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("candidate manifest must be a JSON object")
    if manifest.get("predev_lock_sha256") != sha256_json_file(args.predev_lock):
        raise ValueError("candidate was not frozen against this exact predevelopment lock")
    if manifest.get("bundle_sha256") != sha256_file(args.candidate_bundle):
        raise ValueError("candidate bundle changed after freeze")
    parent = lock.get("parent")
    if not isinstance(parent, dict) or manifest.get("parent_one_weight_sha256") != parent.get(
        "one_weight_sha256"
    ):
        raise ValueError("candidate was not derived from the locked R2.3 parent")

    result = evaluate_frozen_fresh_gate(
        _read_rows(args.parent_results),
        _read_rows(args.candidate_results),
        predev_lock=lock,
        candidate_manifest=manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "output": str(args.output)}, sort_keys=True))
    return 0 if result["promotion_gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
