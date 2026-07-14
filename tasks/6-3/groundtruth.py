#!/usr/bin/env python3
import sys


def solve(value):
    return value.replace("a", "b" if "b" in value else "c")


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
