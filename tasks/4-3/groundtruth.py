#!/usr/bin/env python3
"""Ground truth for task 4-3."""

import sys


def solve(value):
    """Remove the first three characters."""
    return value[3:]


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
