#!/usr/bin/env python3
"""Ground truth for task 3-4."""

import sys


def solve(value):
    """Swap the leading a run with the trailing b run."""
    leading = len(value) - len(value.lstrip("a"))
    trailing = len(value) - len(value.rstrip("b"))
    middle = value[leading:len(value) - trailing]
    return "b" * trailing + middle + "a" * leading


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
