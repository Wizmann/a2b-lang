#!/usr/bin/env python3
"""Ground truth for task 3-6."""

import sys


def solve(value):
    """Keep all occurrences of the unique most frequent letter."""
    counts = {char: value.count(char) for char in "abc"}
    most_common = max(counts, key=counts.get)
    return "".join(char for char in value if char == most_common)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
