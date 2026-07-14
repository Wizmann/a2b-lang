#!/usr/bin/env python3
"""Ground truth for task 1-3."""

import sys


def solve(value):
    """Collapse each run of equal letters to one letter."""
    if not value:
        return value
    result = [value[0]]
    for char in value[1:]:
        if char != result[-1]:
            result.append(char)
    return "".join(result)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
