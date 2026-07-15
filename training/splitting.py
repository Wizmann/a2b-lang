"""Deterministic group-aware data splitting and leakage checks."""

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class SplitConfig:
    train_fraction: float = 0.8
    validation_fraction: float = 0.1
    test_fraction: float = 0.1
    group_by_template_family: bool = True

    def __post_init__(self):
        values = (
            self.train_fraction,
            self.validation_fraction,
            self.test_fraction,
        )
        if any(not isinstance(value, (int, float)) or value < 0 for value in values):
            raise ValueError("split fractions must be non-negative numbers")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError("split fractions must sum to 1")


@dataclass(frozen=True)
class SplitResult:
    train: tuple
    validation: tuple
    test: tuple

    def as_dict(self):
        return {
            "train": self.train,
            "validation": self.validation,
            "test": self.test,
        }


@dataclass(frozen=True)
class LeakageAudit:
    duplicate_ids: int
    duplicate_behaviors: int
    signature_cross_split: int
    template_family_cross_split: int
    public_hidden_overlap: int

    @property
    def passed(self):
        return not any(
            (
                self.duplicate_ids,
                self.duplicate_behaviors,
                self.signature_cross_split,
                self.template_family_cross_split,
                self.public_hidden_overlap,
            )
        )


def _stable_group_order(keys, seed):
    def key(value):
        payload = (str(seed) + "\0" + value).encode("utf-8")
        return hashlib.sha256(payload).digest()

    return sorted(keys, key=key)


def split_problems(problems, *, seed, config=None):
    """Split by template family by default, preventing family leakage."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    config = config or SplitConfig()
    groups = defaultdict(list)
    for problem in problems:
        group = (
            problem.generated_program.template_family
            if config.group_by_template_family
            else problem.behavior_signature
        )
        groups[group].append(problem)

    split_names = ("train", "validation", "test")
    fractions = {
        "train": config.train_fraction,
        "validation": config.validation_fraction,
        "test": config.test_fraction,
    }
    total = len(problems)
    targets = {name: total * fractions[name] for name in split_names}
    assigned = {name: [] for name in split_names}

    ordered_groups = _stable_group_order(groups, seed)
    # Give every non-zero split one group when enough groups exist.
    nonzero = [name for name in split_names if fractions[name] > 0]
    for index, group_name in enumerate(ordered_groups):
        group = groups[group_name]
        if index < len(nonzero) and len(ordered_groups) >= len(nonzero):
            destination = nonzero[index]
        else:
            destination = max(
                nonzero,
                key=lambda name: targets[name] - len(assigned[name]),
            )
        assigned[destination].extend(group)

    for values in assigned.values():
        values.sort(key=lambda problem: problem.id)
    return SplitResult(
        train=tuple(assigned["train"]),
        validation=tuple(assigned["validation"]),
        test=tuple(assigned["test"]),
    )


def audit_leakage(splits):
    """Check duplicate behavior, split crossings, and public/hidden overlap."""
    all_problems = [
        problem
        for problems in splits.as_dict().values()
        for problem in problems
    ]
    id_counts = Counter(problem.id for problem in all_problems)
    signature_counts = Counter(problem.behavior_signature for problem in all_problems)

    signature_splits = defaultdict(set)
    family_splits = defaultdict(set)
    overlap = 0
    for split_name, problems in splits.as_dict().items():
        for problem in problems:
            signature_splits[problem.behavior_signature].add(split_name)
            family_splits[problem.generated_program.template_family].add(split_name)
            public = {case["input"] for case in problem.public_tests}
            hidden = {case["input"] for case in problem.hidden_tests}
            overlap += len(public & hidden)

    return LeakageAudit(
        duplicate_ids=sum(count - 1 for count in id_counts.values() if count > 1),
        duplicate_behaviors=sum(
            count - 1 for count in signature_counts.values() if count > 1
        ),
        signature_cross_split=sum(len(names) > 1 for names in signature_splits.values()),
        template_family_cross_split=sum(len(names) > 1 for names in family_splits.values()),
        public_hidden_overlap=overlap,
    )
