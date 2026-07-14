#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 1-4."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

ALPHABET = "abc"
MIN_LENGTH = 1
MAX_LENGTH = 7
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 1004

MANUAL_CASES = (
    ("a", "单个 a 应保留"),
    ("b", "不含 a"),
    ("c", "不含 a"),
    ("aa", "最短连续 a 段"),
    ("aaa", "连续 a 段"),
    ("ba", "末尾单个 a 应保留"),
    ("ab", "开头单个 a 应保留"),
    ("aaabcaa", "题面样例"),
    ("baaba", "题面样例"),
    ("aaaaaaa", "最大长度且全部为连续 a"),
    ("aabaa", "两个连续 a 段"),
    ("abaca", "两个单独 a 均保留"),
    ("aab", "开头连续 a 段"),
    ("baa", "结尾连续 a 段"),
    ("aaba", "连续 a 段后接单个 a"),
    ("abaa", "单个 a 后接连续 a 段"),
    ("abcabc", "不含连续 a"),
    ("caaac", "中间连续 a 段"),
    ("aacaaba", "多个连续段与单个 a 混合"),
    ("ccaaacc", "最长中间连续 a 段"),
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
