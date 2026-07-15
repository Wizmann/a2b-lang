"""Quality statistics for generated problems and split artifacts."""

from collections import Counter
from dataclasses import asdict

from .splitting import audit_leakage


def quality_statistics(problems, splits=None):
    problems = tuple(problems)
    count = len(problems)
    line_distribution = Counter()
    step_distribution = Counter()
    identities = 0.0
    terminating = 0.0
    constant_problems = 0
    overlaps = 0
    signatures = Counter()

    for problem in problems:
        quality = problem.quality
        identities += quality.identity_fraction
        terminating += quality.terminating_fraction
        constant_problems += quality.distinct_outputs == 1
        overlaps += quality.public_hidden_overlap
        line_distribution[quality.program_lines] += 1
        step_distribution.update(quality.execution_steps)
        signatures[problem.behavior_signature] += 1

    result = {
        "problem_count": count,
        "identity_fraction": identities / count if count else 0.0,
        "constant_fraction": constant_problems / count if count else 0.0,
        "terminating_fraction": terminating / count if count else 0.0,
        "program_line_distribution": dict(sorted(line_distribution.items())),
        "execution_step_distribution": dict(sorted(step_distribution.items())),
        "public_hidden_overlap": overlaps,
        "behavior_duplicates": sum(
            value - 1 for value in signatures.values() if value > 1
        ),
    }
    if splits is not None:
        result["split_sizes"] = {
            name: len(values) for name, values in splits.as_dict().items()
        }
        leakage = audit_leakage(splits)
        result["leakage_audit"] = asdict(leakage)
        result["leakage_audit"]["passed"] = leakage.passed
    return result
