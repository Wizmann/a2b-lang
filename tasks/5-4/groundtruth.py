#!/usr/bin/env python3
"""Ground truth for task 5-4."""

import sys


def solve(value):
    left, right = value.split("-")
    return format(int(left, 2) - int(right, 2), "b")


if __name__ == "__main__":
    print(solve(sys.stdin.readline().strip()))
