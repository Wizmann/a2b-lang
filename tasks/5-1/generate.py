#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 5-1."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

MIN_VALUE = 1
MAX_VALUE = 63
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 5001

MANUAL_CASES = (
    "1", "10", "11", "100", "101", "110", "111", "1000", "1111", "10000",
    "11111", "100000", "101010", "110011", "111111", "100001", "101101",
    "110110", "111000", "111111",
)


def generate_cases(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        yield format(rng.randint(MIN_VALUE, MAX_VALUE), "b")


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
