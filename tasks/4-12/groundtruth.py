#!/usr/bin/env python3
"""Ground truth for task 4-12."""

import sys


def solve(value):
    """Replace a with b when any b exists, otherwise replace a with c."""
    replacement = "b" if "b" in value else "c"
    return value.replace("a", replacement)


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
