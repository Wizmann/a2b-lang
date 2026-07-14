#!/usr/bin/env python3
"""Ground truth for task 4-5."""

import sys


def solve(value):
    """Swap the first and last characters."""
    if len(value) < 2:
        return value
    return value[-1] + value[1:-1] + value[0]


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
