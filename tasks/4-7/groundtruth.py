#!/usr/bin/env python3
"""Ground truth for task 4-7."""

import sys


def solve(value):
    """Remove the third character."""
    return value[:2] + value[3:]


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
