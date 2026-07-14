#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 5-3."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

MIN_VALUE = 1
MAX_VALUE = 31
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 5003

MANUAL_CASES = (
    "1+1", "1+10", "10+1", "10+10", "11+1", "11+10", "111+1", "111+101",
    "1000+1", "1000+111", "1111+1", "1111+1111", "10000+1", "10000+11111",
    "11111+1", "11111+11111", "10101+10101", "11010+10101", "10001+1110", "1010+10101",
)


def generate_cases(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        left = format(rng.randint(MIN_VALUE, MAX_VALUE), "b")
        right = format(rng.randint(MIN_VALUE, MAX_VALUE), "b")
        yield left + "+" + right


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
