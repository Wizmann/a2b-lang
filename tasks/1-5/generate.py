#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 1-5."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

ALPHABET = "abc"
MIN_LENGTH = 1
MAX_LENGTH = 7
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 1005

MANUAL_CASES = (
    ("a", "单个 a"),
    ("b", "单个 b"),
    ("c", "单个 c"),
    ("abc", "已经有序"),
    ("cba", "完全逆序"),
    ("caba", "题面样例"),
    ("abccba", "题面样例"),
    ("aaaaaaa", "最大长度且全部为 a"),
    ("ccccccc", "最大长度且全部为 c"),
    ("cbacbac", "最大长度混合输入"),
    ("aaab", "a 与 b 的重复组合"),
    ("bbbc", "b 与 c 的重复组合"),
    ("ccca", "c 与 a 的重复组合"),
    ("baca", "两端均需交换"),
    ("acacac", "交替的 a 与 c"),
    ("bcbcbcb", "最大长度交替的 b 与 c"),
    ("cabac", "多次交换且含重复字母"),
    ("abcabca", "混合字符的最大长度输入"),
    ("ccabbaa", "三类字母均逆序分布"),
    ("bacabcb", "多种局部逆序"),
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
