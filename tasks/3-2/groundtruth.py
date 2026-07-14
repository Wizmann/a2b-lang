#!/usr/bin/env python3
"""Ground truth for task 3-2."""

import sys


def solve(value):
    """Rotate left through the first a, preserving the suffix order."""
    index = value.index("a")
    return value[index:] + value[:index]


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
