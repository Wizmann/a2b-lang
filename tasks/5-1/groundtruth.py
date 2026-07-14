#!/usr/bin/env python3
"""Ground truth for task 5-1."""

import sys


def solve(value):
    return "a" * int(value, 2)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().strip()))
