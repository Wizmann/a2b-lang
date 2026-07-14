#!/usr/bin/env python3
"""Ground truth for task 2-3."""

import sys


def solve(value):
    """Return true exactly for inputs of length three."""
    return "true" if len(value) == 3 else "false"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
