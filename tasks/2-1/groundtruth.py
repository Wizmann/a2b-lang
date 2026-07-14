#!/usr/bin/env python3
"""Ground truth for task 2-1."""

import sys


def solve(value):
    """Return the fixed greeting, regardless of the valid input."""
    return "helloworld"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
