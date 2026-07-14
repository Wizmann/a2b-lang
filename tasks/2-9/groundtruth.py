#!/usr/bin/env python3
"""Ground truth for task 2-9."""

import sys


def solve(value):
    """Return the unique least frequent letter."""
    counts = {char: value.count(char) for char in "abc"}
    return min(counts, key=counts.get)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
