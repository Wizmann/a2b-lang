#!/usr/bin/env python3
import argparse,json,random
from pathlib import Path
from groundtruth import solve
MANUAL_CASES=("ab","ba","aa","bb","cc","abc","cba","abba","cbabc","abca","aab","baa","abcba","ababa","acbca","ccc","abcabc","aabb","bcb","cabac")
def generate_cases(count,seed):
 r=random.Random(seed)
 for _ in range(count):yield ''.join(r.choice('abc') for _ in range(r.randint(2,7)))
def write(p,vs):
 with p.open('w',encoding='utf-8') as f:
  for v in vs:f.write(json.dumps({'input':v,'output':solve(v)})+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=200);p.add_argument('--seed',type=int,default=6002);p.add_argument('--directory',type=Path,default=Path(__file__).parent);a=p.parse_args();a.directory.mkdir(parents=True,exist_ok=True);write(a.directory/'testcase_pretest.jsonl',MANUAL_CASES[:10]);write(a.directory/'testcase_full.jsonl',list(MANUAL_CASES)+list(generate_cases(a.count,a.seed)))
if __name__=='__main__':main()
