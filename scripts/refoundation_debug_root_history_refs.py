from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nolane.repository.audit_v2 import (  # noqa: E402
    _QUOTED_TOKEN,
    _expected_archive_target,
    _history_locations,
    _iter_reference_text,
    _root_dynamic_category_for_token,
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
            for match in _QUOTED_TOKEN.finditer(cleaned):
                token = match.group("token")
                category = _root_dynamic_category_for_token(token)
                if category is not None:
                    hits.append(
                        {
                            "category": category,
                            "path": relative.as_posix(),
                            "line": line_number,
                            "token": token,
                            "text": line.strip(),
                        }
                    )
    print(json.dumps(hits, indent=2, sort_keys=True))
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
