#!/usr/bin/env python3
"""Ground truth for task 4-10."""

import sys


def solve(value):
    """Keep characters at even one-based positions."""
    return value[1::2]


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
