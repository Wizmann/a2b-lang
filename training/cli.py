"""可复现的数据生成、审计与报告命令。"""

import argparse
import json
from pathlib import Path

from .cognitive_smoke import (
    audit_cognitive_smoke,
    record_cognitive_test_results,
    write_cognitive_smoke,
)


def command_generate(args):
    result = write_cognitive_smoke(
        Path.cwd(),
        args.output,
        seed=args.seed,
    )
    summary = {
        "synthesis_problem_count": result["statistics"][
            "synthesis_problem_count"
        ],
        "cognitive_family_count": result["statistics"][
            "cognitive_family_count"
        ],
        "semantic_archetype_count": result["statistics"][
            "semantic_archetype_count"
        ],
        "review_checks_passed": result["checks"]["passed"],
        "audit_passed": result["audit"]["passed"],
        "artifact_directory": str(args.output.resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["checks"]["passed"] and result["audit"]["passed"] else 2


def command_audit(args):
    result = audit_cognitive_smoke(args.artifact_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 2


def command_report(args):
    path = record_cognitive_test_results(
        args.artifact_dir,
        passed=args.passed,
        failed=args.failed,
        skipped=args.skipped,
        duration=args.duration,
    )
    print(path)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="A=B 训练数据工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("dataset-generate", help="生成认知原型冒烟数据")
    generate.add_argument("--seed", type=int, default=20260715)
    generate.add_argument("--output", type=Path, required=True)
    generate.set_defaults(func=command_generate)

    audit = subparsers.add_parser("dataset-audit", help="重新审计已有数据产物")
    audit.add_argument("--artifact-dir", type=Path, required=True)
    audit.set_defaults(func=command_audit)

    report = subparsers.add_parser("dataset-report", help="记录测试结果并刷新中文报告")
    report.add_argument("--artifact-dir", type=Path, required=True)
    report.add_argument("--passed", type=int, required=True)
    report.add_argument("--failed", type=int, default=0)
    report.add_argument("--skipped", type=int, default=0)
    report.add_argument("--duration", required=True)
    report.set_defaults(func=command_report)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
