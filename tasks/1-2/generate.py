#!/usr/bin/env python3
"""Generate deterministic JSONL test sets for task 1-2."""

import argparse
import json
import random
from pathlib import Path

from groundtruth import solve

ALPHABET = "abc"
MIN_LENGTH = 1
MAX_LENGTH = 7
DEFAULT_CASE_COUNT = 200
DEFAULT_SEED = 1002

MANUAL_CASES = (
    ("a", "单个 a"),
    ("b", "单个 b"),
    ("c", "单个 c"),
    ("aa", "全部为 a"),
    ("bb", "全部为 b"),
    ("cc", "全部为 c"),
    ("abc", "题面样例"),
    ("aabbcc", "题面样例"),
    ("abca", "循环顺序且 a 位于两端"),
    ("cbacba", "逆序重复"),
    ("aaaaaaa", "最大长度且全部为 a"),
    ("bbbbbbb", "最大长度且全部为 b"),
    ("ccccccc", "最大长度且全部为 c"),
    ("aab", "a 与 b 的连续组合"),
    ("bbc", "b 与 c 的连续组合"),
    ("cca", "c 与 a 的连续组合"),
    ("abcabca", "混合字符的最大长度输入"),
    ("cabac", "a 位于 c 之间"),
    ("bcacb", "单个内部 a"),
    ("acbbcca", "多种连续段"),
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
