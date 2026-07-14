#!/usr/bin/env python3
import sys


def solve(value):
    left, right = value.split("/")
    dividend, divisor = int(left, 2), int(right, 2)
    return format(dividend // divisor, "b") + "," + format(dividend % divisor, "b")


if __name__ == "__main__":
    print(solve(sys.stdin.readline().strip()))
