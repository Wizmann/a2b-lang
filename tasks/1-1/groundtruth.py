#!/usr/bin/env python3
"""Ground truth for task 1-1."""

import sys


def solve(value):
    """Replace every 'a' in a valid input string with 'b'."""
    return value.replace("a", "b")


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
