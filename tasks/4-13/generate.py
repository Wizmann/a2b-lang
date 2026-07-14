#!/usr/bin/env python3
import argparse, json, random
from pathlib import Path
from groundtruth import solve

DEFAULT_CASE_COUNT, DEFAULT_SEED = 200, 4013
MANUAL_CASES = ("a", "b", "c", "abc", "cba", "aaa", "aba", "abcba", "ababa", "cbabc", "aabaa", "bacab", "acbca", "bbbbb", "ccccccc", "aaaaaaa", "abcabca", "cbacabc", "abababa", "cacacac")

def generate_cases(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        n = rng.choice((1, 3, 5, 7))
        yield "".join(rng.choice("abc") for _ in range(n))

def write(path, values):
    with path.open("w", encoding="utf-8") as f:
        for v in values: f.write(json.dumps({"input":v,"output":solve(v)})+"\n")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=DEFAULT_CASE_COUNT); p.add_argument("--seed",type=int,default=DEFAULT_SEED); p.add_argument("--directory",type=Path,default=Path(__file__).parent); a=p.parse_args(); a.directory.mkdir(parents=True,exist_ok=True); write(a.directory/"testcase_pretest.jsonl",MANUAL_CASES[:10]); write(a.directory/"testcase_full.jsonl",list(MANUAL_CASES)+list(generate_cases(a.count,a.seed)))
if __name__ == "__main__": main()
