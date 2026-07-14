#!/usr/bin/env python3
"""Ground truth for task 2-6."""

import sys


def solve(value):
    """Return true iff exactly one equal-letter run has length one."""
    singleton_runs = 0
    index = 0
    while index < len(value):
        end = index + 1
        while end < len(value) and value[end] == value[index]:
            end += 1
        if end - index == 1:
            singleton_runs += 1
        index = end
    return "true" if singleton_runs == 1 else "false"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
