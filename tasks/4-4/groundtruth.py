#!/usr/bin/env python3
"""Ground truth for task 4-4."""

import sys


def solve(value):
    """Remove up to three occurrences of ``a``, starting from the right."""
    characters = list(value)
    remaining = 3
    for index in range(len(characters) - 1, -1, -1):
        if characters[index] == "a":
            del characters[index]
            remaining -= 1
            if remaining == 0:
                break
    return "".join(characters)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
