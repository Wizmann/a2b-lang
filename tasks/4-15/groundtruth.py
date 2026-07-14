#!/usr/bin/env python3
"""Ground truth for task 4-15."""

import sys


def solve(value):
    """Repeat the character at position i exactly i times (1-indexed)."""
    return "".join(char * (index + 1) for index, char in enumerate(value))


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
