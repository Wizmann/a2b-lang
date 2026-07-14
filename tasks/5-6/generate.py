#!/usr/bin/env python3
import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

MIN_VALUE = 1
MAX_VALUE = 31
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 5006
MANUAL_CASES = (
    "1/1", "10/1", "10/10", "10/11", "11/10", "1000/11", "1111/10", "1111/11",
    "10000/11", "11111/1", "11111/11111", "10101/10", "10101/101", "11010/10101",
    "10001/1110", "1010/10101", "111/10000", "100/111", "1001/1001", "11011/1011",
)


def generate_cases(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        a = rng.randint(MIN_VALUE, MAX_VALUE)
        b = rng.randint(MIN_VALUE, MAX_VALUE)
        yield format(a, "b") + "/" + format(b, "b")


def write_cases(path, values):
    with path.open("w", encoding="utf-8") as f:
        for value in values:
            f.write(json.dumps({"input": value, "output": solve(value)}) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=DEFAULT_CASE_COUNT)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--directory", type=Path, default=Path(__file__).parent)
    args = p.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    write_cases(args.directory / "testcase_pretest.jsonl", MANUAL_CASES[:10])
    write_cases(args.directory / "testcase_full.jsonl", list(MANUAL_CASES) + list(generate_cases(args.count, args.seed)))


if __name__ == "__main__":
    main()
