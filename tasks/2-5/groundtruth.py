#!/usr/bin/env python3
"""Ground truth for task 2-5."""

import sys


def solve(value):
    """Return true when every letter count is odd or zero."""
    return "true" if all(value.count(char) % 2 == 1 or value.count(char) == 0
                          for char in "abc") else "false"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
