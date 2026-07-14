#!/usr/bin/env python3
"""Ground truth for task 3-5."""

import sys


def solve(value):
    """Return true iff the first and last letters are equal."""
    return "true" if value[0] == value[-1] else "false"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
