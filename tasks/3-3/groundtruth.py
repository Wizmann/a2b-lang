#!/usr/bin/env python3
"""Ground truth for task 3-3."""

import sys


def solve(value):
    """Replace leading and trailing runs of a with b."""
    leading = len(value) - len(value.lstrip("a"))
    trailing = len(value) - len(value.rstrip("a"))
    if leading + trailing >= len(value):
        return "b" * len(value)
    return "b" * leading + value[leading:len(value) - trailing] + "b" * trailing


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
