#!/usr/bin/env python3
"""Ground truth for task 4-9."""

import sys


def solve(value):
    """Swap every a and b while preserving c."""
    return value.translate(str.maketrans({"a": "b", "b": "a"}))


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
