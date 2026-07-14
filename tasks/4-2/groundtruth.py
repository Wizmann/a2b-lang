#!/usr/bin/env python3
"""Ground truth for task 4-2."""

import sys


def solve(value):
    """Remove up to the first three occurrences of a."""
    removed = 0
    result = []
    for char in value:
        if char == "a" and removed < 3:
            removed += 1
        else:
            result.append(char)
    return "".join(result)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
