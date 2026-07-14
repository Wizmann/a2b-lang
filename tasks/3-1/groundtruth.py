#!/usr/bin/env python3
"""Ground truth for task 3-1."""

import sys


def solve(value):
    """Strip all leading and trailing lowercase a characters."""
    return value.strip("a")


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
