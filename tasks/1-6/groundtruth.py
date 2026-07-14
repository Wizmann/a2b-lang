#!/usr/bin/env python3
"""Ground truth for task 1-6."""

import sys


def solve(value):
    """Return the letter occurring more often; inputs never tie."""
    count_a = value.count("a")
    count_b = value.count("b")
    if count_a == count_b:
        raise ValueError("input must have unequal a and b counts")
    return "a" if count_a > count_b else "b"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
