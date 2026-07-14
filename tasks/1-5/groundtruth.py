#!/usr/bin/env python3
"""Ground truth for task 1-5."""

import sys


def solve(value):
    """Return the input letters sorted in ascending a < b < c order."""
    return "".join(sorted(value))


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
