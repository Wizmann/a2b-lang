#!/usr/bin/env python3
"""Ground truth for task 2-8."""

import sys


def solve(value):
    """Return the uniquely most frequent letter."""
    return max("abc", key=value.count)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
