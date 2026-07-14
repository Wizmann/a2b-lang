#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 5-4."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

MIN_VALUE = 1
MAX_VALUE = 31
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 5004

MANUAL_CASES = (
    "10-1", "11-1", "11-10", "100-1", "100-11", "101-1", "101-10", "111-1",
    "1000-1", "1000-11", "1001-10", "1010-11", "1100-101", "1111-1", "1111-111",
    "10000-1", "10000-1111", "10101-101", "11010-10101", "11111-1",
)


def generate_cases(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        left = rng.randint(2, MAX_VALUE)
        right = rng.randint(1, left - 1)
        yield format(left, "b") + "-" + format(right, "b")


def write_cases(output, values):
    with output.open("w", encoding="utf-8") as f:
        for value in values:
            f.write(json.dumps({"input": value, "output": solve(value)}) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=DEFAULT_CASE_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--directory", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    write_cases(args.directory / "testcase_pretest.jsonl", MANUAL_CASES[:10])
    write_cases(args.directory / "testcase_full.jsonl", list(MANUAL_CASES) + list(generate_cases(args.count, args.seed)))


if __name__ == "__main__":
    main()
