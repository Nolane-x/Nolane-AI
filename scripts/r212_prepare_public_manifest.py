from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from cogcoder.r212_real_repo_protocol import redact_dataset_row


def prepare_public_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    public = [redact_dataset_row(row) for row in rows]
    ids = [row['instance_id'] for row in public]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate instance_id in dataset')
    return public


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    source_path = Path(args.input)
    raw = source_path.read_bytes()
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise ValueError('dataset root must be a list')
    public = prepare_public_rows(rows)
    payload = {
        'schema': 'nolane-r212-public-real-repo-panel-v1',
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'tasks': public,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
