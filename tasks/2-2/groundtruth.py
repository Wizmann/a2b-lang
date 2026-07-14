#!/usr/bin/env python3
"""Ground truth for task 2-2."""

import sys


def solve(value):
    """Return true exactly when the input contains at least three a's."""
    return "true" if value.count("a") >= 3 else "false"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
