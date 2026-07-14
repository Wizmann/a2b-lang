#!/usr/bin/env python3
"""Ground truth for task 3-7."""

import sys


def solve(value):
    """Return true iff the input is a palindrome."""
    return "true" if value == value[::-1] else "false"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
