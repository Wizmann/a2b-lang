#!/usr/bin/env python3
"""Ground truth for task 1-4."""

import sys


def solve(value):
    """Remove every run of at least two consecutive 'a' characters."""
    result = []
    index = 0
    while index < len(value):
        if value[index] != "a":
            result.append(value[index])
            index += 1
            continue
        end = index
        while end < len(value) and value[end] == "a":
            end += 1
        if end - index == 1:
            result.append("a")
        index = end
    return "".join(result)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
