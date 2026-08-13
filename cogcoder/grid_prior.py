from __future__ import annotations


def preferred_background(histogram) -> int:
    if 0 in histogram:
        return 0
    return min(histogram, key=lambda color: (-histogram[color], color))
