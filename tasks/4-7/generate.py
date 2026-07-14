#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 4-7."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

ALPHABET = "abc"
MIN_LENGTH = 3
MAX_LENGTH = 7
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 4007

MANUAL_CASES = (
    "aaa", "abc", "cba", "abca", "acbc", "abcabc", "aabbcc", "bbbcbbb",
    "ababaaa", "ccbcca", "cccab", "acabbb", "abbaabc", "acabb", "aabaacb",
    "cabcccb", "aaccabc", "ccbaaaa", "cbbaa", "bbbbbbb",
)


def generate_cases(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        length = rng.randint(MIN_LENGTH, MAX_LENGTH)
        yield "".join(rng.choice(ALPHABET) for _ in range(length))


def write_cases(output, values):
    with output.open("w", encoding="utf-8") as output_file:
        for value in values:
            output_file.write(json.dumps({"input": value, "output": solve(value)}) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=DEFAULT_CASE_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--directory", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    write_cases(args.directory / "testcase_pretest.jsonl", MANUAL_CASES[:10])
    write_cases(
        args.directory / "testcase_full.jsonl",
        list(MANUAL_CASES) + list(generate_cases(args.count, args.seed)),
    )


if __name__ == "__main__":
    main()
