#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 1-3."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

ALPHABET = "abc"
MIN_LENGTH = 1
MAX_LENGTH = 7
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 1003

MANUAL_CASES = (
    ("a", "单个字符"),
    ("b", "单个字符"),
    ("c", "单个字符"),
    ("aa", "最短重复段"),
    ("bb", "最短重复段"),
    ("cc", "最短重复段"),
    ("ab", "没有重复段"),
    ("abc", "没有重复段"),
    ("aaa", "单个最大重复段"),
    ("aabbbcc", "题面样例"),
    ("abccba", "题面样例"),
    ("aaaaaaa", "最大长度且全部相同"),
    ("bbbbbbb", "最大长度且全部相同"),
    ("ccccccc", "最大长度且全部相同"),
    ("aabb", "两个重复段"),
    ("bbcc", "两个重复段"),
    ("aabbcc", "三个重复段"),
    ("ccaabb", "逆序的三个重复段"),
    ("aaabaaa", "同一字母的重复段被不同字母分隔"),
    ("abbaaac", "多个不同长度的重复段"),
)


def generate_cases(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        length = rng.randint(MIN_LENGTH, MAX_LENGTH)
        yield "".join(rng.choice(ALPHABET) for _ in range(length))


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
