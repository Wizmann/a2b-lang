#!/usr/bin/env python3
import sys


def solve(value):
    middle = len(value) // 2
    return value[:middle] + value[middle + 1:]


if __name__ == "__main__":
    print(solve(sys.stdin.readline().rstrip("\n")))
