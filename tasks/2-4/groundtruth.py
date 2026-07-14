#!/usr/bin/env python3
"""Ground truth for task 2-4."""

import sys


def solve(value):
    """Return the remainder of the input length divided by three."""
    return str(len(value) % 3)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
