#!/usr/bin/env python3
"""Ground truth for task 4-6."""

import sys


def solve(value):
    """Reverse the input string."""
    return value[::-1]


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
