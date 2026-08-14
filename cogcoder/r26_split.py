from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


def partition_name(filename: str) -> str:
    """Return the preregistered R2.6 partition using only the basename."""
    name = Path(filename).name
    digest = hashlib.sha256(name.encode('utf-8')).hexdigest()
    bucket = int(digest[:8], 16) % 5
    return 'internal_heldout' if bucket == 4 else 'development'


def partition_paths(paths: Iterable[Path]) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Sort paths by basename and split without reading file contents."""
    development: list[Path] = []
    heldout: list[Path] = []
    for path in sorted((Path(p) for p in paths), key=lambda p: p.name):
        if partition_name(path.name) == 'internal_heldout':
            heldout.append(path)
        else:
            development.append(path)
    return tuple(development), tuple(heldout)
