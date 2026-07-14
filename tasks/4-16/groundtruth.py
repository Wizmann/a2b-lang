#!/usr/bin/env python3
"""Ground truth for task 4-16."""

import sys


def solve(value):
    """Interleave the equal-length strings on either side of the comma."""
    left, right = value.split(",")
    return "".join(a + b for a, b in zip(left, right))


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
