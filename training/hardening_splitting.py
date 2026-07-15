"""Lineage-safe controlled benchmarks for Semantic Hardening."""

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass

from A2B import parse

from .dataset import execute_with_limits


HARDENING_SPLITS = (
    "train",
    "validation",
    "test_alpha_renaming",
    "test_description_style",
    "test_length",
    "test_operation_order",
    "test_composition",
    "test_parameter_holdout",
)


@dataclass(frozen=True)
class HardeningSplitResult:
    splits: dict
    controlled_benchmarks: dict

    def as_dict(self):
        return self.splits


def _stable(value, seed):
    return hashlib.sha256((str(seed) + "\0" + value).encode("utf-8")).digest()


def _operation_sequence(problem):
    return tuple(problem.generated_program.parameters.get("operation_sequence", ()))


def _parameter_key(problem):
    parameters = problem.generated_program.parameters
    ir = parameters.get("ir", {})
    return json.dumps(
        {
            "family": problem.generated_program.algorithm_family,
            "operations": ir.get("operations", []),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _rename_markers(program, markers):
    replacements = {}
    candidates = iter("!@$%^&*|?~QWERTYUIOPASDFGHJKLZXCVBNM")
    for marker in markers:
        replacement = next(value for value in candidates if value not in program)
        replacements[marker] = replacement
    return "".join(replacements.get(char, char) for char in program), replacements


def _alternate_description(description):
    if description.startswith("输入：") and "\n输出：" in description:
        input_text, output_text = description.split("\n输出：", 1)
        return "给定%s，%s" % (input_text[len("输入：") :], output_text)
    if "。" in description:
        input_text, output_text = description.split("。", 1)
        return "输入：%s。\n输出：%s" % (input_text, output_text)
    return "输出要求：" + description


def _equivalent_on_problem_cases(problem, variant_program):
    left = parse(problem.generated_program.program)
    right = parse(variant_program)
    maximum = problem.generated_program.limits["max_string_length"]
    for case in tuple(problem.public_tests) + tuple(problem.hidden_tests):
        left_result = execute_with_limits(
            left, case["input"], max_steps=10000, max_length=maximum
        )
        right_result = execute_with_limits(
            right, case["input"], max_steps=10000, max_length=maximum
        )
        if (
            not left_result.terminating
            or not right_result.terminating
            or left_result.output != right_result.output
        ):
            return False
    return True


def split_hardening_problems(problems, *, seed):
    problems = tuple(problems)
    by_id = {problem.id: problem for problem in problems}
    alpha_groups = defaultdict(list)
    for problem in problems:
        alpha_groups[problem.hardening["alpha_equivalence_class"]].append(problem)
    assignment = {}
    benchmarks = {name: [] for name in HARDENING_SPLITS if name.startswith("test_")}

    def assign_group(problem, split):
        group = alpha_groups[problem.hardening["alpha_equivalence_class"]]
        existing = {assignment[item.id] for item in group if item.id in assignment}
        if existing and existing != {split}:
            return False
        for item in group:
            assignment[item.id] = split
        return True

    # Alpha benchmark: both concrete marker views remain in the same test split.
    alpha_selected = 0
    for group in sorted(alpha_groups.values(), key=lambda values: _stable(values[0].id, seed)):
        marked = [
            problem
            for problem in group
            if problem.generated_program.parameters.get("marker_allocation")
        ]
        if not marked:
            continue
        problem = marked[0]
        variant, renaming = _rename_markers(
            problem.generated_program.program,
            problem.generated_program.parameters["marker_allocation"],
        )
        if variant == problem.generated_program.program or not assign_group(
            problem, "test_alpha_renaming"
        ):
            continue
        benchmarks["test_alpha_renaming"].append(
            {
                "root_problem_id": problem.id,
                "split": "test_alpha_renaming",
                "base_program": problem.generated_program.program,
                "variant_program": variant,
                "marker_renaming": renaming,
                "only_changed": "internal_markers",
                "verified_equivalent": _equivalent_on_problem_cases(
                    problem, variant
                ),
            }
        )
        alpha_selected += 1
        if alpha_selected >= 8:
            break

    # Operation-order benchmark: compare the same components with another order.
    order_selected = 0
    for problem in sorted(problems, key=lambda item: _stable(item.id, seed + 1)):
        if problem.id in assignment or not problem.hardening["order_sensitive"]:
            continue
        if problem.generated_program.composition_depth < 2:
            continue
        if not assign_group(problem, "test_operation_order"):
            continue
        family = "order:" + hashlib.sha256(
            json.dumps(
                sorted(_operation_sequence(problem)),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        problem.hardening["mutant_family_id"] = family
        benchmarks["test_operation_order"].append(
            {
                "root_problem_id": problem.id,
                "split": "test_operation_order",
                "components": list(_operation_sequence(problem)),
                "comparison_order": problem.hardening["order_comparison"],
                "distinguishing_input": problem.hardening[
                    "order_distinguishing_input"
                ],
                "outputs_on_distinguishing_input": problem.hardening[
                    "order_outputs"
                ],
                "oracle_proved_different": True,
            }
        )
        order_selected += 1
        if order_selected >= 8:
            break

    # Composition benchmark: component anchors are train-only; composition is test-only.
    anchors = defaultdict(list)
    for problem in problems:
        sequence = _operation_sequence(problem)
        if len(sequence) == 1:
            anchors[sequence[0]].append(problem)
    composition_selected = 0
    for problem in sorted(problems, key=lambda item: _stable(item.id, seed + 2)):
        sequence = _operation_sequence(problem)
        if (
            problem.id in assignment
            or len(sequence) < 2
            or not problem.hardening["genuine_composition"]
            or not all(anchors[kind] for kind in set(sequence))
        ):
            continue
        chosen = []
        conflict = False
        for kind in dict.fromkeys(sequence):
            anchor = next(
                (
                    value
                    for value in anchors[kind]
                    if value.id not in assignment
                ),
                None,
            )
            if anchor is None or not assign_group(anchor, "train"):
                conflict = True
                break
            chosen.append(anchor.id)
        if conflict or not assign_group(problem, "test_composition"):
            continue
        benchmarks["test_composition"].append(
            {
                "root_problem_id": problem.id,
                "split": "test_composition",
                "component_train_problem_ids": chosen,
                "components": list(sequence),
                "combination_absent_from_train": True,
            }
        )
        composition_selected += 1
        if composition_selected >= 8:
            break

    # Same program, disjoint short/long evaluation domains.
    length_selected = 0
    for problem in sorted(problems, key=lambda item: _stable(item.id, seed + 3)):
        if problem.id in assignment:
            continue
        construction = problem.hardening["construction_domain"]["max_length"]
        generalization = problem.hardening["generalization_domain"]["max_length"]
        if generalization <= construction or not assign_group(problem, "test_length"):
            continue
        benchmarks["test_length"].append(
            {
                "root_problem_id": problem.id,
                "split": "test_length",
                "program": problem.generated_program.program,
                "train_length_range": [
                    problem.hardening["construction_domain"]["min_length"],
                    construction,
                ],
                "test_length_range": [construction + 1, generalization],
                "only_changed": "input_length",
            }
        )
        length_selected += 1
        if length_selected >= 12:
            break

    # Same problem, alternate functional wording; both views share one split.
    style_selected = 0
    for problem in sorted(problems, key=lambda item: _stable(item.id, seed + 4)):
        if problem.id in assignment or problem.hardening["specification_level"] != "functional":
            continue
        if not assign_group(problem, "test_description_style"):
            continue
        benchmarks["test_description_style"].append(
            {
                "root_problem_id": problem.id,
                "split": "test_description_style",
                "base_description": problem.generated_program.description,
                "variant_description": _alternate_description(
                    problem.generated_program.description
                ),
                "only_changed": "description_style",
            }
        )
        style_selected += 1
        if style_selected >= 12:
            break

    # Same algorithm family; one concrete parameter bucket is unseen in train.
    families = defaultdict(list)
    for problem in problems:
        if problem.id not in assignment:
            families[problem.generated_program.algorithm_family].append(problem)
    parameter_selected = 0
    for family, values in sorted(families.items()):
        buckets = defaultdict(list)
        for problem in values:
            buckets[_parameter_key(problem)].append(problem)
        if len(buckets) < 2:
            continue
        keys = sorted(buckets, key=lambda value: _stable(value, seed + 5))
        train_problem = buckets[keys[0]][0]
        test_problem = buckets[keys[-1]][0]
        if not assign_group(train_problem, "train") or not assign_group(
            test_problem, "test_parameter_holdout"
        ):
            continue
        benchmarks["test_parameter_holdout"].append(
            {
                "algorithm_family": family,
                "train_problem_id": train_problem.id,
                "test_problem_id": test_problem.id,
                "only_changed": "algorithm_parameter",
            }
        )
        parameter_selected += 1
        if parameter_selected >= 10:
            break

    remaining = [problem for problem in problems if problem.id not in assignment]
    remaining.sort(key=lambda item: _stable(item.id, seed + 6))
    validation_count = max(12, len(problems) // 20)
    for problem in remaining[:validation_count]:
        assign_group(problem, "validation")
    for problem in problems:
        if problem.id not in assignment:
            assign_group(problem, "train")

    splits = {name: [] for name in HARDENING_SPLITS}
    for problem in problems:
        splits[assignment[problem.id]].append(problem)
    return HardeningSplitResult(
        splits={
            name: tuple(sorted(values, key=lambda item: item.id))
            for name, values in splits.items()
        },
        controlled_benchmarks={
            name: tuple(values) for name, values in benchmarks.items()
        },
    )


def _locations(split_result, field):
    locations = defaultdict(set)
    for split, problems in split_result.as_dict().items():
        for problem in problems:
            locations[problem.hardening[field]].add(split)
    return locations


def confounding_report(split_result):
    train = split_result.as_dict()["train"]

    def profile(problems):
        return {
            "source_type": dict(Counter(p.generated_program.source_type for p in problems)),
            "domain": dict(Counter(p.generated_program.task_domain for p in problems)),
            "program_length": dict(
                Counter(len(p.generated_program.program.splitlines()) for p in problems)
            ),
            "difficulty": dict(Counter(p.generated_program.difficulty for p in problems)),
            "description_style": dict(
                Counter(p.generated_program.description_style for p in problems)
            ),
        }

    train_profile = profile(train)
    result = {}
    for name, problems in split_result.as_dict().items():
        if not name.startswith("test_"):
            continue
        split_profile = profile(problems)
        differences = {
                field: sorted(
                    set(train_profile[field]) ^ set(split_profile[field])
                )
                for field in train_profile
        }
        result[name] = {
            "train": train_profile,
            "split": split_profile,
            "differences": differences,
            "confounding_detected": any(differences.values()),
            "primary_control": "paired_or_matched_benchmark",
        }
    return result


def audit_hardening_splits(split_result, auxiliary=None):
    lineage = _locations(split_result, "program_lineage_id")
    mutants = _locations(split_result, "mutant_family_id")
    alpha = _locations(split_result, "alpha_equivalence_class")
    problem_split = {
        problem.id: split
        for split, problems in split_result.as_dict().items()
        for problem in problems
    }
    auxiliary_reference_cross_split = 0
    if auxiliary:
        for records in auxiliary.values():
            for record in records:
                root = record["root_problem_id"]
                lineage[record["program_lineage_id"]].add(record["split"])
                mutants[record["mutant_family_id"]].add(record["split"])
                alpha[record["alpha_equivalence_class"]].add(record["split"])
                if root in problem_split and record["split"] != problem_split[root]:
                    auxiliary_reference_cross_split += 1
    operation_benchmarks = split_result.controlled_benchmarks[
        "test_operation_order"
    ]
    alpha_benchmarks = split_result.controlled_benchmarks[
        "test_alpha_renaming"
    ]
    checks = {
        "lineage_cross_split": sum(len(values) > 1 for values in lineage.values()),
        "mutant_family_cross_split": sum(
            len(values) > 1 for values in mutants.values()
        ),
        "auxiliary_reference_cross_split": auxiliary_reference_cross_split,
        "alpha_equivalent_program_cross_split": sum(
            len(values) > 1 for values in alpha.values()
        ),
        "operation_order_unproved": sum(
            not item["oracle_proved_different"]
            or item["distinguishing_input"] is None
            for item in operation_benchmarks
        ),
        "alpha_pair_unverified": sum(
            not item["verified_equivalent"] for item in alpha_benchmarks
        ),
        "split_sizes": {
            name: len(values) for name, values in split_result.as_dict().items()
        },
    }
    checks["passed"] = (
        not any(
            checks[name]
            for name in (
                "lineage_cross_split",
                "mutant_family_cross_split",
                "auxiliary_reference_cross_split",
                "alpha_equivalent_program_cross_split",
                "operation_order_unproved",
                "alpha_pair_unverified",
            )
        )
        and all(checks["split_sizes"].values())
    )
    return checks
