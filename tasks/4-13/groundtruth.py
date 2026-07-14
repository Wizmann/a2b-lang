#!/usr/bin/env python3
import sys


def solve(value):
    return value[len(value) // 2]


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
