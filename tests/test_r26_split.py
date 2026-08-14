from __future__ import annotations

import hashlib

from cogcoder.r26_split import partition_name


def expected(name: str) -> str:
    digest = hashlib.sha256(name.encode('utf-8')).hexdigest()
    bucket = int(digest[:8], 16) % 5
    return 'internal_heldout' if bucket == 4 else 'development'


def test_split_is_filename_only_and_stable() -> None:
    assert partition_name('abc123.json') == partition_name('abc123.json')
    assert partition_name('abc123.json') in {'development', 'internal_heldout'}


def test_split_matches_independent_formula() -> None:
    names = [f'{i:08x}.json' for i in range(20)]
    for name in names:
        assert partition_name(name) == expected(name)


def main() -> None:
    test_split_is_filename_only_and_stable()
    test_split_matches_independent_formula()
    print('R2.6 split tests PASS')


if __name__ == '__main__':
    main()
