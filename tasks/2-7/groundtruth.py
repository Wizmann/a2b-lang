#!/usr/bin/env python3
"""Ground truth for task 2-7."""

import sys


def solve(value):
    """Return true iff counts strictly increase from a to b to c."""
    count_a = value.count("a")
    count_b = value.count("b")
    count_c = value.count("c")
    return "true" if count_a < count_b < count_c else "false"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
