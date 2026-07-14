#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 1-6."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

ALPHABET = "ab"
MIN_LENGTH = 1
MAX_LENGTH = 11
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 1006

MANUAL_CASES = (
    ("a", "最短输入，a 占多数"),
    ("b", "最短输入，b 占多数"),
    ("aa", "全部为 a"),
    ("bb", "全部为 b"),
    ("aaa", "a 以最小优势取胜"),
    ("bbb", "b 以最小优势取胜"),
    ("abb", "题面样例"),
    ("ababa", "题面样例"),
    ("aaaaaaaaaaa", "最大长度且全部为 a"),
    ("bbbbbbbbbbb", "最大长度且全部为 b"),
    ("aab", "a 比 b 多一个"),
    ("abbba", "b 比 a 多一个"),
    ("aaaaabbbb", "较大数量差，a 占多数"),
    ("aaaabbbbb", "较大数量差，b 占多数"),
    ("abababa", "交替输入且 a 占多数"),
    ("bababab", "交替输入且 b 占多数"),
    ("aaaaaabbbbb", "最大长度附近，a 多一个"),
    ("aaaaabbbbbb", "最大长度附近，b 多一个"),
    ("aabbababa", "混合顺序，a 占多数"),
    ("bbababbab", "混合顺序，b 占多数"),
)


def generate_cases(count, seed):
    rng = random.Random(seed)
    generated = 0
    while generated < count:
        length = rng.randint(MIN_LENGTH, MAX_LENGTH)
        value = "".join(rng.choice(ALPHABET) for _ in range(length))
        if value.count("a") == value.count("b"):
            continue
        generated += 1
        yield value


def write_cases(output, values):
    with output.open("w", encoding="utf-8") as output_file:
        for value in values:
            case = {"input": value, "output": solve(value)}
            output_file.write(json.dumps(case, ensure_ascii=False) + "\n")


def write_pretest(output):
    write_cases(output, [value for value, _ in MANUAL_CASES[:10]])


def write_full(output, count, seed):
    manual_values = [value for value, _ in MANUAL_CASES]
    write_cases(output, manual_values + list(generate_cases(count, seed)))


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
