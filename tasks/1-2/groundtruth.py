#!/usr/bin/env python3
"""Ground truth for task 1-2."""

import sys


def solve(value):
    """Convert every valid lowercase input letter to uppercase."""
    return value.replace("a", "A").replace("b", "B").replace("c", "C")


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
