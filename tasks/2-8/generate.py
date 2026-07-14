#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 2-8."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

ALPHABET = "abc"
MIN_LENGTH = 1
MAX_LENGTH = 7
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 2008

MANUAL_CASES = (
    "a", "b", "c", "aa", "bb", "cc", "bbc", "cacbca", "ababa", "cbccc",
    "aaaabcc", "bbbacba", "cccaab", "aacba", "bcbbb", "caccc", "aaaaabc",
    "bbbbbca", "cccccab", "abcabca",
)


def has_unique_maximum(value):
    counts = [value.count(letter) for letter in ALPHABET]
    return counts.count(max(counts)) == 1


def generate_cases(count, seed):
    rng = random.Random(seed)
    generated = 0
    while generated < count:
        length = rng.randint(MIN_LENGTH, MAX_LENGTH)
        value = "".join(rng.choice(ALPHABET) for _ in range(length))
        if has_unique_maximum(value):
            generated += 1
            yield value


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
