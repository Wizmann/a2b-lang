#!/usr/bin/env python3
"""Ground truth for task 4-11."""

import sys


def solve(value):
    """Repeat the input string once."""
    return value + value


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
