#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 3-6."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

ALPHABET = "abc"
MIN_LENGTH = 1
MAX_LENGTH = 7
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 3006

MANUAL_CASES = (
    "a",
    "b",
    "c",
    "aaab",
    "bbbc",
    "ccca",
    "cabcca",
    "bbc",
    "abbbac",
    "aaaaaaa",
    "bbbbbbb",
    "ccccccc",
    "aabac",
    "abbcb",
    "accbca",
    "aaaabbc",
    "abbbbcc",
    "cacccab",
    "bbababc",
    "cccabca",
)


def is_valid(value):
    counts = [value.count(char) for char in ALPHABET]
    return counts.count(max(counts)) == 1


def generate_cases(count, seed):
    rng = random.Random(seed)
    generated = 0
    while generated < count:
        length = rng.randint(MIN_LENGTH, MAX_LENGTH)
        value = "".join(rng.choice(ALPHABET) for _ in range(length))
        if not is_valid(value):
            continue
        generated += 1
        yield value


def write_cases(output, values):
    with output.open("w", encoding="utf-8") as output_file:
        for value in values:
            case = {"input": value, "output": solve(value)}
            output_file.write(json.dumps(case, ensure_ascii=False) + "\n")


def write_pretest(output):
    write_cases(output, MANUAL_CASES[:10])


def write_full(output, count, seed):
    write_cases(output, list(MANUAL_CASES) + list(generate_cases(count, seed)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=DEFAULT_CASE_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--directory", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()

    args.directory.mkdir(parents=True, exist_ok=True)
    write_pretest(args.directory / "testcase_pretest.jsonl")
    write_full(args.directory / "testcase_full.jsonl", args.count, args.seed)


if __name__ == "__main__":
    main()
