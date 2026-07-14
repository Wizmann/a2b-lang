#!/usr/bin/env python3
"""Ground truth for task 4-8."""

import sys


def solve(value):
    """Append a copy of the first three characters."""
    return value + value[:3]


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
