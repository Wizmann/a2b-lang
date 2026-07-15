"""语义加固统计与退出检查。"""

from collections import Counter, defaultdict

from .baselines import run_baselines
from .hardening_splitting import confounding_report


def _baseline_dict(results):
    return [
        {
            "baseline": result.baseline,
            "attempted": result.attempted,
            "public_solved": result.public_solved,
            "hidden_solved": result.hidden_solved,
            "public_only_overfit": result.public_only_overfit,
        }
        for result in results
    ]


def baselines_by_specification(problems):
    groups = defaultdict(list)
    for problem in problems:
        groups[problem.hardening["specification_level"]].append(problem)
    return {
        level: _baseline_dict(run_baselines(values))
        for level, values in sorted(groups.items())
    }


def teacher_rates_by_specification(problems, teacher_results=()):
    solved = {item["problem_id"]: bool(item["solved"]) for item in teacher_results}
    result = {}
    for level in ("functional", "io_only", "operational"):
        ids = [
            problem.id
            for problem in problems
            if problem.hardening["specification_level"] == level
            and problem.id in solved
        ]
        passed = sum(solved[problem_id] for problem_id in ids)
        result[level] = {
            "attempted": len(ids),
            "passed": passed,
            "pass_rate": passed / len(ids) if ids else None,
            "real_teacher_tested": bool(ids),
        }
    return result


def _length_category(problem):
    generated = problem.generated_program
    family = generated.algorithm_family
    if family in {"random_dfa", "random_fst"}:
        return "dfa_fst"
    if family in {"reversal", "binary_reverse"}:
        return "reversal"
    if family == "symbol_sort":
        return "sorting"
    if "normalizer" in family:
        return "normalization"
    if generated.task_domain in {"unary_arithmetic", "binary_operations"}:
        return "arithmetic"
    if generated.composition_depth > 1:
        return "composition"
    return None


def length_audit(problems):
    result = {}
    for category in (
        "dfa_fst",
        "reversal",
        "sorting",
        "normalization",
        "arithmetic",
        "composition",
    ):
        values = [problem for problem in problems if _length_category(problem) == category]
        result[category] = {
            "problem_count": len(values),
            "construction_max_lengths": sorted(
                {p.hardening["construction_domain"]["max_length"] for p in values}
            ),
            "public_max_lengths": sorted(
                {p.hardening["public_domain"]["max_length"] for p in values}
            ),
            "hidden_max_lengths": sorted(
                {p.hardening["hidden_domain"]["max_length"] for p in values}
            ),
            "generalization_max_lengths": sorted(
                {p.hardening["generalization_domain"]["max_length"] for p in values}
            ),
            "audit_max_lengths": sorted(
                {p.hardening["audit_domain"]["max_length"] for p in values}
            ),
            "all_verified": all(
                p.hardening["audit_reference_verification"]["fraction"] == 1.0
                for p in values
            ),
            "has_longer_than_construction": bool(values)
            and all(
                p.hardening["audit_domain"]["max_length"]
                > p.hardening["construction_domain"]["max_length"]
                for p in values
            ),
        }
    return result


def hardening_statistics(
    problems,
    split_result,
    split_audit,
    *,
    teacher_results=(),
):
    problems = tuple(problems)
    compositions = [
        problem
        for problem in problems
        if problem.generated_program.composition_depth > 1
    ]
    specification = Counter(
        problem.hardening["specification_level"] for problem in problems
    )
    composition_classes = Counter(
        problem.hardening["component_interaction"] for problem in compositions
    )
    genuine = sum(
        problem.hardening["genuine_composition"] for problem in compositions
    )
    superficial = sum(
        problem.hardening["superficial_composition"] for problem in compositions
    )
    return {
        "problem_count": len(problems),
        "specification_level_counts": dict(specification),
        "solution_revealing_score_distribution": dict(
            Counter(problem.hardening["solution_revealing_score"] for problem in problems)
        ),
        "composition": {
            "problem_count": len(compositions),
            "genuine_count": genuine,
            "superficial_count": superficial,
            "genuine_fraction": genuine / len(compositions) if compositions else 0.0,
            "superficial_fraction": superficial / len(compositions) if compositions else 0.0,
            "classes": dict(composition_classes),
            "all_effective_depth_at_least_two": all(
                problem.hardening["effective_composition_depth"] >= 2
                for problem in compositions
            ),
            "all_depth_three_components_effective": all(
                problem.generated_program.composition_depth != 3
                or len(problem.hardening["effective_components"]) == 3
                for problem in compositions
            ),
        },
        "fingerprints": {
            "concrete_behavior_unique": len(
                {p.hardening["concrete_behavior_fingerprint"] for p in problems}
            ),
            "alpha_normalized_behavior_unique": len(
                {
                    p.hardening["alpha_normalized_behavior_fingerprint"]
                    for p in problems
                }
            ),
            "structural_unique": len({p.structural_fingerprint for p in problems}),
            "semantic_ir_unique": len(
                {p.hardening["semantic_ir_fingerprint"] for p in problems}
            ),
        },
        "behavior_duplicates": len(problems)
        - len({p.hardening["concrete_behavior_fingerprint"] for p in problems}),
        "ontology_error_count": sum(
            len(problem.hardening["ontology_errors"]) for problem in problems
        ),
        "reference_verification_fraction": sum(
            problem.hardening["audit_reference_verification"]["fraction"] == 1.0
            for problem in problems
        )
        / len(problems),
        "split_sizes": {
            name: len(values) for name, values in split_result.as_dict().items()
        },
        "split_audit": split_audit,
        "controlled_benchmark_counts": {
            name: len(values)
            for name, values in split_result.controlled_benchmarks.items()
        },
        "confounding_report": confounding_report(split_result),
        "length_audit": length_audit(problems),
        "baseline_by_specification": baselines_by_specification(problems),
        "teacher_by_specification": teacher_rates_by_specification(
            problems, teacher_results
        ),
    }


def hardening_exit_checks(statistics):
    length = statistics["length_audit"]
    checks = {
        "count_240_to_500": 240 <= statistics["problem_count"] <= 500,
        "reference_verification_100_percent": statistics[
            "reference_verification_fraction"
        ]
        == 1.0,
        "behavior_duplicates_zero": statistics["behavior_duplicates"] == 0,
        "cross_split_lineage_leakage_zero": statistics["split_audit"][
            "lineage_cross_split"
        ]
        == 0,
        "mutant_family_leakage_zero": statistics["split_audit"][
            "mutant_family_cross_split"
        ]
        == 0,
        "auxiliary_reference_leakage_zero": statistics["split_audit"][
            "auxiliary_reference_cross_split"
        ]
        == 0,
        "alpha_equivalent_leakage_zero": statistics["split_audit"][
            "alpha_equivalent_program_cross_split"
        ]
        == 0,
        "ontology_errors_zero": statistics["ontology_error_count"] == 0,
        "all_compositions_effective": statistics["composition"][
            "all_effective_depth_at_least_two"
        ],
        "all_depth_three_components_effective": statistics["composition"][
            "all_depth_three_components_effective"
        ],
        "all_operation_order_proved_sensitive": statistics["split_audit"][
            "operation_order_unproved"
        ]
        == 0,
        "genuine_composition_reported": statistics["composition"][
            "genuine_count"
        ]
        > 0,
        "operational_descriptions_reported": "operational"
        in statistics["specification_level_counts"],
        "confounding_report_generated": bool(statistics["confounding_report"]),
        "long_domain_categories_verified": all(
            item["problem_count"] > 0
            and item["all_verified"]
            and item["has_longer_than_construction"]
            for item in length.values()
        ),
    }
    checks["passed"] = all(checks.values()) and statistics["split_audit"]["passed"]
    return checks
