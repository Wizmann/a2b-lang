#!/usr/bin/env python3
"""Ground truth for task 5-2."""

import sys


def solve(value):
    return format(int(value, 2) + 1, "b")


if __name__ == "__main__":
    print(solve(sys.stdin.readline().strip()))
