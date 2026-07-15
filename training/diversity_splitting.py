"""面向泛化评测的数据切分。"""

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass


GENERALIZATION_SPLITS = (
    "train",
    "validation",
    "test_instance",
    "test_family",
    "test_length",
    "test_parameter_holdout",
    "test_alpha_renaming",
    "test_composition",
    "test_operation_order",
    "test_concept_holdout",
    "test_description_style",
    "test_program_length",
)


@dataclass(frozen=True)
class DiversitySplitResult:
    splits: dict
    held_out_concepts: tuple
    held_out_description_style: str

    def as_dict(self):
        return self.splits


def _stable(value, seed):
    encoded = (str(seed) + "\0" + value).encode("utf-8")
    return hashlib.sha256(encoded).digest()


def _sequence(problem):
    return tuple(problem.generated_program.parameters.get("operation_sequence", ()))


def _markers(problem):
    return tuple(problem.generated_program.parameters.get("marker_allocation", ()))


def _parameter_key(problem):
    parameters = problem.generated_program.parameters
    ir = parameters.get("ir") or {}
    operation_buckets = []
    for operation in ir.get("operations", []):
        values = operation.get("parameters", {})
        bucket = {"kind": operation.get("kind")}
        if "mapping" in values:
            bucket["mapping_size"] = len(values["mapping"])
            bucket["distinct_targets"] = len(set(values["mapping"].values()))
        if "symbols" in values:
            bucket["symbol_count"] = len(values["symbols"])
        if "old" in values:
            bucket["old_length"] = len(values["old"])
            bucket["new_length"] = len(values.get("new", ""))
        if "pattern" in values:
            bucket["pattern_length"] = len(values["pattern"])
        if "states" in values:
            bucket["state_count"] = len(values["states"])
            bucket["mode"] = values.get("mode")
        if "operation" in values:
            bucket["operation"] = values["operation"]
        operation_buckets.append(bucket)
    properties = parameters.get("behavior_properties", {})
    return json.dumps(
        {
            "family": problem.generated_program.algorithm_family,
            "operations": operation_buckets,
            "behavior_cluster": sorted(
                name for name, enabled in properties.items() if enabled
            ),
            "max_input_length": parameters.get("max_input_length"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def split_diversity_problems(problems, *, seed):
    problems = tuple(problems)
    by_id = {problem.id: problem for problem in problems}
    assignment = {}
    force_train = set()

    # Preserve the existing instance/family/input-length generalization views.
    held_out_family = "reversal"
    for problem in problems:
        if problem.generated_program.algorithm_family == held_out_family:
            assignment[problem.id] = "test_family"
    maximum_domain_length = max(
        problem.generated_program.parameters.get("max_input_length", 0)
        for problem in problems
    )
    for problem in problems:
        if (
            problem.id not in assignment
            and problem.generated_program.parameters.get("max_input_length")
            == maximum_domain_length
        ):
            assignment[problem.id] = "test_length"

    # Completely hold out the precise rule-list description regime.
    held_out_style = "rules"
    for problem in problems:
        if (
            problem.id not in assignment
            and problem.generated_program.description_style == held_out_style
        ):
            assignment[problem.id] = "test_description_style"

    # Fully hold out one substantive computation concept.
    held_out_concept = "finite_state_machine"
    for problem in problems:
        if held_out_concept in problem.generated_program.concepts:
            assignment[problem.id] = "test_concept_holdout"

    # Same components, unseen order: keep one order in train and reverse in test.
    sequence_groups = defaultdict(list)
    for problem in problems:
        sequence = _sequence(problem)
        if len(sequence) >= 2 and problem.id not in assignment:
            sequence_groups[tuple(sorted(sequence))].append(problem)
    operation_order_count = 0
    for group in sequence_groups.values():
        sequences = defaultdict(list)
        for problem in group:
            sequences[_sequence(problem)].append(problem)
        keys = sorted(sequences)
        for left in keys:
            right = tuple(reversed(left))
            if right in sequences and right != left:
                train_problem = sequences[left][0]
                test_problem = sequences[right][0]
                force_train.add(train_problem.id)
                assignment[test_problem.id] = "test_operation_order"
                operation_order_count += 1
                break
        if operation_order_count >= 8:
            break

    # Reserve a complete long program-line bucket before composition consumes it.
    forced_lengths = {
        len(by_id[problem_id].generated_program.program.splitlines())
        for problem_id in force_train
    }
    length_candidates = [
        problem
        for problem in problems
        if problem.id not in assignment and problem.id not in force_train
    ]
    candidate_length_counts = Counter(
        len(problem.generated_program.program.splitlines())
        for problem in length_candidates
    )
    eligible_lengths = [
        length
        for length, count in candidate_length_counts.items()
        if length not in forced_lengths and count >= 2
    ]
    if eligible_lengths:
        held_out_program_length = max(eligible_lengths)
        for problem in length_candidates:
            if len(problem.generated_program.program.splitlines()) == held_out_program_length:
                assignment[problem.id] = "test_program_length"

    # Hold out complete operation sequences while retaining each component alone.
    single_kind_anchors = defaultdict(list)
    for problem in problems:
        sequence = _sequence(problem)
        if len(sequence) == 1 and problem.id not in assignment:
            single_kind_anchors[sequence[0]].append(problem)
    composition_sequences = []
    for problem in sorted(problems, key=lambda item: _stable(item.id, seed)):
        sequence = _sequence(problem)
        sequence_has_forced_train = any(
            other.id in force_train and _sequence(other) == sequence
            for other in problems
        )
        if (
            len(sequence) >= 2
            and problem.id not in assignment
            and all(single_kind_anchors[kind] for kind in set(sequence))
            and sequence not in composition_sequences
            and not sequence_has_forced_train
        ):
            composition_sequences.append(sequence)
        if len(composition_sequences) >= 10:
            break
    for problem in problems:
        sequence = _sequence(problem)
        if sequence in composition_sequences and problem.id not in force_train:
            assignment[problem.id] = "test_composition"
            for kind in set(sequence):
                force_train.add(single_kind_anchors[kind][0].id)

    # Alpha-renaming: same canonical structure, different concrete marker tuple.
    structural_groups = defaultdict(list)
    global_marker_counts = Counter(
        _markers(problem) for problem in problems if _markers(problem)
    )
    for problem in problems:
        if problem.id not in assignment and _markers(problem):
            structural_groups[problem.structural_fingerprint].append(problem)
    alpha_count = 0
    for group in structural_groups.values():
        allocations = defaultdict(list)
        for problem in group:
            allocations[_markers(problem)].append(problem)
        keys = list(allocations)
        if len(keys) < 2:
            continue
        test_keys = [key for key in keys[1:] if global_marker_counts[key] == 1]
        if not test_keys:
            continue
        train_problem = allocations[keys[0]][0]
        test_problem = allocations[test_keys[0]][0]
        force_train.add(train_problem.id)
        assignment[test_problem.id] = "test_alpha_renaming"
        alpha_count += 1
        if alpha_count >= 10:
            break

    # Parameter holdout within families that retain another parameterization.
    families = defaultdict(list)
    for problem in problems:
        if problem.id not in assignment:
            families[problem.generated_program.algorithm_family].append(problem)
    parameter_count = 0
    for family, values in sorted(families.items()):
        buckets = defaultdict(list)
        for problem in values:
            buckets[_parameter_key(problem)].append(problem)
        if len(buckets) < 2:
            continue
        ordered_buckets = sorted(buckets, key=lambda value: _stable(value, seed + 1))
        train_bucket = ordered_buckets[0]
        test_bucket = ordered_buckets[-1]
        force_train.add(buckets[train_bucket][0].id)
        for problem in buckets[test_bucket]:
            assignment[problem.id] = "test_parameter_holdout"
        parameter_count += 1
        if parameter_count >= 12:
            break

    # Exact marker allocations selected for alpha holdout must not occur in train.
    alpha_allocations = {
        _markers(by_id[problem_id])
        for problem_id, split in assignment.items()
        if split == "test_alpha_renaming"
    }
    for problem in problems:
        if (
            problem.id not in assignment
            and problem.id not in force_train
            and _markers(problem) in alpha_allocations
        ):
            assignment[problem.id] = "test_alpha_renaming"

    remaining = [
        problem
        for problem in problems
        if problem.id not in assignment and problem.id not in force_train
    ]
    remaining.sort(key=lambda item: _stable(item.id, seed + 4))
    instance_count = max(5, len(problems) // 25)
    for problem in remaining[:instance_count]:
        assignment[problem.id] = "test_instance"
    remaining = remaining[instance_count:]
    validation_count = max(5, len(problems) // 20)
    for problem in remaining[:validation_count]:
        assignment[problem.id] = "validation"
    for problem in problems:
        if problem.id not in assignment:
            assignment[problem.id] = "train"

    splits = {name: [] for name in GENERALIZATION_SPLITS}
    for problem in problems:
        splits[assignment[problem.id]].append(problem)
    for values in splits.values():
        values.sort(key=lambda item: item.id)
    return DiversitySplitResult(
        splits={name: tuple(values) for name, values in splits.items()},
        held_out_concepts=(held_out_concept,),
        held_out_description_style=held_out_style,
    )


def audit_diversity_splits(result):
    splits = result.as_dict()
    behavior_locations = defaultdict(set)
    ids = Counter()
    for name, problems in splits.items():
        for problem in problems:
            ids[problem.id] += 1
            behavior_locations[problem.behavior_signature].add(name)

    train = splits["train"]
    train_sequences = {_sequence(problem) for problem in train}
    train_kinds = {kind for sequence in train_sequences for kind in sequence}
    composition = splits["test_composition"]
    operation_order = splits["test_operation_order"]
    alpha = splits["test_alpha_renaming"]
    train_markers = {_markers(problem) for problem in train if _markers(problem)}
    held_out = set(result.held_out_concepts)
    held_out_families = {
        problem.generated_program.algorithm_family
        for problem in splits["test_family"]
    }
    train_families = {
        problem.generated_program.algorithm_family for problem in train
    }
    held_out_lengths = {
        problem.generated_program.parameters.get("max_input_length")
        for problem in splits["test_length"]
    }
    train_lengths = {
        problem.generated_program.parameters.get("max_input_length")
        for problem in train
    }
    train_parameter_keys = {_parameter_key(problem) for problem in train}
    train_styles = {
        problem.generated_program.description_style for problem in train
    }
    program_test_lengths = [
        len(problem.generated_program.program.splitlines())
        for problem in splits["test_program_length"]
    ]
    train_program_lengths = [
        len(problem.generated_program.program.splitlines()) for problem in train
    ]
    train_concepts = {
        concept for problem in train for concept in problem.generated_program.concepts
    }

    checks = {
        "duplicate_ids": sum(value - 1 for value in ids.values() if value > 1),
        "behavior_cross_split": sum(
            len(locations) > 1 for locations in behavior_locations.values()
        ),
        "composition_sequence_seen_in_train": sum(
            _sequence(problem) in train_sequences for problem in composition
        ),
        "composition_component_missing_from_train": sum(
            any(kind not in train_kinds for kind in _sequence(problem))
            for problem in composition
        ),
        "operation_order_seen_in_train": sum(
            _sequence(problem) in train_sequences for problem in operation_order
        ),
        "operation_order_without_permutation_in_train": sum(
            not any(
                sorted(_sequence(problem)) == sorted(sequence)
                and _sequence(problem) != sequence
                for sequence in train_sequences
            )
            for problem in operation_order
        ),
        "alpha_marker_allocation_seen_in_train": sum(
            _markers(problem) in train_markers for problem in alpha
        ),
        "held_out_concept_seen_in_train": len(held_out & train_concepts),
        "held_out_family_seen_in_train": len(held_out_families & train_families),
        "held_out_input_length_seen_in_train": len(held_out_lengths & train_lengths),
        "held_out_parameter_seen_in_train": sum(
            _parameter_key(problem) in train_parameter_keys
            for problem in splits["test_parameter_holdout"]
        ),
        "held_out_description_style_seen_in_train": int(
            result.held_out_description_style in train_styles
        ),
        "program_length_holdout_seen_in_train": len(
            set(program_test_lengths) & set(train_program_lengths)
        ),
        "program_length_split_empty": int(
            not program_test_lengths
        ),
    }
    checks["split_sizes"] = {name: len(values) for name, values in splits.items()}
    checks["held_out_concepts"] = sorted(held_out)
    numeric_failures = [
        value for key, value in checks.items() if key not in {"split_sizes", "held_out_concepts"}
    ]
    checks["passed"] = not any(numeric_failures) and all(
        checks["split_sizes"][name] > 0 for name in GENERALIZATION_SPLITS
    )
    return checks
