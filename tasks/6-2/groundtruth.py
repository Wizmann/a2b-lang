#!/usr/bin/env python3
import sys


def solve(value):
    return "true" if value == value[::-1] else "false"


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
