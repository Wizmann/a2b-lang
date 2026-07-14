#!/usr/bin/env python3
"""Ground truth for task 4-1."""

import sys


def solve(value):
    """Prefix the input with hello."""
    return "hello" + value


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
