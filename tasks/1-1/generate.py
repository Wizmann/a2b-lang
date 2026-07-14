#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 1-1."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

ALPHABET = "abc"
MIN_LENGTH = 1
MAX_LENGTH = 7
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 1001

MANUAL_CASES = (
    ("a", "单个 a"),
    ("b", "单个不变的 b"),
    ("c", "单个不变的 c"),
    ("aa", "全部字符均需替换"),
    ("ab", "a 位于开头"),
    ("ba", "a 位于结尾"),
    ("aca", "多个分离的 a"),
    ("bbb", "不含 a"),
    ("aaaaaaa", "最大长度且全部为 a"),
    ("ccccccc", "最大长度且不含 a"),
    ("aab", "连续 a 位于开头"),
    ("aba", "a 位于两端"),
    ("baa", "连续 a 位于结尾"),
    ("abc", "题面样例"),
    ("aabb", "题面样例"),
    ("cba", "a 前有不变前缀"),
    ("bcacb", "单个内部 a"),
    ("cabac", "a 位于 c 之间"),
    ("abcabca", "混合字符的最大长度输入"),
    ("cbcbcbc", "不含 a 的最大长度输入"),
)


def generate_cases(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        length = rng.randint(MIN_LENGTH, MAX_LENGTH)
        input_value = "".join(rng.choice(ALPHABET) for _ in range(length))
        yield input_value


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
    parser.add_argument("--directory", type=Path,
                        default=Path(__file__).parent)
    args = parser.parse_args()

    args.directory.mkdir(parents=True, exist_ok=True)
    write_pretest(args.directory / "testcase_pretest.jsonl")
    write_full(args.directory / "testcase_full.jsonl", args.count, args.seed)


if __name__ == "__main__":
    main()
