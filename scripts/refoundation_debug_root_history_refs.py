from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nolane.repository.audit_v2 import (  # noqa: E402
    _DYNAMIC_FAMILY_PATTERNS,
    _expected_archive_target,
    _history_locations,
    _iter_reference_text,
    _strip_archive_qualified_references,
)


def main() -> int:
    locations = _history_locations(ROOT)
    targets = tuple(_expected_archive_target(name) for name in locations)
    hits: list[dict[str, object]] = []
    for relative, text in _iter_reference_text(ROOT):
        for line_number, line in enumerate(text.splitlines(), start=1):
            cleaned = _strip_archive_qualified_references(line, targets)
            if "archive/root-history/" in cleaned:
                continue
            for category, pattern in _DYNAMIC_FAMILY_PATTERNS:
                if pattern.search(cleaned):
                    hits.append(
                        {
                            "category": category,
                            "path": relative.as_posix(),
                            "line": line_number,
                            "text": line.strip(),
                        }
                    )
    print(json.dumps(hits, indent=2, sort_keys=True))
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
