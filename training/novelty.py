"""Novelty inventory, scoring, and teacher-innovation proposal verification."""

import json
from collections import Counter
from dataclasses import dataclass

from A2B import A2BParseException, parse

from .dataset import InputPoolConfig, ProblemBuildConfig, build_problem
from .generation import FailureReason, GeneratedProgram, GenerationRejected


@dataclass(frozen=True)
class NoveltyScore:
    concept_novelty: float
    composition_novelty: float
    structural_novelty: float
    behavior_novelty: float
    nearest_distance: float
    total: float


def novelty_inventory(problems):
    concepts = Counter()
    families = Counter()
    compositions = Counter()
    structures = Counter()
    for problem in problems:
        generated = problem.generated_program
        concepts.update(generated.concepts)
        families[generated.algorithm_family] += 1
        compositions[tuple(generated.parameters.get("operation_sequence", ()))] += 1
        structures[problem.structural_fingerprint] += 1
    return {
        "concepts": dict(concepts),
        "algorithm_families": dict(families),
        "compositions": {" -> ".join(key): value for key, value in compositions.items()},
        "structural_clusters": dict(structures),
    }


def _jaccard_distance(left, right):
    left, right = set(left), set(right)
    if not left and not right:
        return 0.0
    return 1.0 - len(left & right) / len(left | right)


def _sequence_distance(left, right):
    left, right = tuple(left), tuple(right)
    if not left and not right:
        return 0.0
    size = max(len(left), len(right))
    matches = sum(a == b for a, b in zip(left, right))
    return 1.0 - matches / size


def score_novelty(candidate, existing):
    existing = tuple(existing)
    generated = candidate.generated_program
    known_concepts = {
        concept for problem in existing for concept in problem.generated_program.concepts
    }
    concepts = set(generated.concepts)
    concept_novelty = (
        len(concepts - known_concepts) / len(concepts) if concepts else 0.0
    )
    sequence = tuple(generated.parameters.get("operation_sequence", ()))
    known_sequences = {
        tuple(problem.generated_program.parameters.get("operation_sequence", ()))
        for problem in existing
    }
    composition_novelty = float(sequence not in known_sequences)
    structures = {problem.structural_fingerprint for problem in existing}
    behaviors = {problem.behavior_signature for problem in existing}
    structural_novelty = float(candidate.structural_fingerprint not in structures)
    behavior_novelty = float(candidate.behavior_signature not in behaviors)

    if existing:
        distances = []
        for problem in existing:
            other = problem.generated_program
            distances.append(
                0.6 * _jaccard_distance(concepts, other.concepts)
                + 0.4
                * _sequence_distance(
                    sequence, other.parameters.get("operation_sequence", ())
                )
            )
        nearest = min(distances)
    else:
        nearest = 1.0
    total = (
        concept_novelty
        + composition_novelty
        + structural_novelty
        + behavior_novelty
        + nearest
    ) / 5.0
    return NoveltyScore(
        concept_novelty=concept_novelty,
        composition_novelty=composition_novelty,
        structural_novelty=structural_novelty,
        behavior_novelty=behavior_novelty,
        nearest_distance=nearest,
        total=total,
    )


def build_novelty_teacher_prompt(language_description, existing_problems):
    inventory = novelty_inventory(existing_problems)
    summary = {
        "concepts": inventory["concepts"],
        "algorithm_families": inventory["algorithm_families"],
        "compositions": inventory["compositions"],
    }
    return f"""{language_description}

Existing data inventory:
{json.dumps(summary, ensure_ascii=False, sort_keys=True)}

Propose one genuinely novel A=B synthesis task. Requirements:
- do not use a simple character renaming;
- do not make a constant-substitution variant of an existing task;
- combine at least two computational concepts;
- provide the program, input alphabet/domain, boundary inputs, concept labels,
  a termination argument, and the difference from the nearest existing family;
- expected outputs are optional and will be ignored because labels are produced locally.

Return one JSON object with fields: program, description, input_alphabet,
min_input_length, max_input_length, boundary_inputs, concepts,
required_features, algorithm_family, task_domain, description_style,
termination_reason, nearest_difference.
"""


def extract_teacher_proposal(content):
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1])
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("teacher proposal must be an object")
    return value


def verify_teacher_proposal(proposal, rng, config, existing_problems=()):
    """Ignore teacher labels and derive all I/O with the local interpreter."""
    required = {
        "program",
        "description",
        "input_alphabet",
        "min_input_length",
        "max_input_length",
        "boundary_inputs",
        "concepts",
        "required_features",
        "algorithm_family",
        "task_domain",
        "description_style",
        "termination_reason",
        "nearest_difference",
    }
    missing = required - set(proposal)
    if missing:
        raise GenerationRejected(
            FailureReason.VERIFIER_FAILURE,
            "teacher proposal missing: %s" % ", ".join(sorted(missing)),
        )
    concepts = proposal["concepts"]
    if not isinstance(concepts, list) or len(set(concepts)) < 2:
        raise GenerationRejected(
            FailureReason.TRIVIAL_BEHAVIOR,
            "teacher proposal must contain at least two concepts",
        )
    if not proposal["termination_reason"].strip():
        raise GenerationRejected(
            FailureReason.NO_TERMINATING_INPUTS, "missing termination reason"
        )
    if len(proposal["program"].splitlines()) > config.max_program_lines:
        raise GenerationRejected(FailureReason.RESOURCE_LIMIT, "program line limit")
    if len(proposal["program"]) > config.max_program_characters:
        raise GenerationRejected(
            FailureReason.RESOURCE_LIMIT, "program character limit"
        )
    try:
        parse(proposal["program"])
    except A2BParseException as error:
        raise GenerationRejected(FailureReason.SYNTAX_ERROR, str(error)) from error

    alphabet = proposal["input_alphabet"]
    minimum = proposal["min_input_length"]
    maximum = min(proposal["max_input_length"], config.max_string_length)
    if (
        not 1 <= len(alphabet) <= 4
        or not all(
            isinstance(char, str)
            and len(char) == 1
            and ord(char) < 128
            and char not in "=#()"
            for char in alphabet
        )
        or maximum < minimum
    ):
        raise GenerationRejected(FailureReason.VERIFIER_FAILURE, "invalid input domain")
    domain_size = sum(len(alphabet) ** length for length in range(minimum, maximum + 1))
    if domain_size > 4096:
        raise GenerationRejected(
            FailureReason.RESOURCE_LIMIT,
            "teacher finite verification domain exceeds 4096 inputs",
        )
    public_count = min(12, max(2, domain_size // 4))
    hidden_count = min(48, domain_size - public_count)
    if hidden_count <= 0:
        raise GenerationRejected(FailureReason.INSUFFICIENT_HIDDEN_TESTS)
    generated = GeneratedProgram(
        program=proposal["program"],
        template_family="teacher_novel",
        template_version="1.0.0",
        generator_name="novelty_teacher",
        generator_version="1.0.0",
        difficulty=min(5, 2 + len(proposal["program"].splitlines()) // 8),
        allowed_features=tuple(proposal["required_features"]),
        parameters={
            "input_alphabet": list(alphabet),
            "min_input_length": minimum,
            "max_input_length": maximum,
            "boundary_inputs": list(proposal["boundary_inputs"]),
            "operation_sequence": list(proposal.get("operation_sequence", [])),
            "marker_allocation": [],
            "termination_reason": proposal["termination_reason"],
            "nearest_difference": proposal["nearest_difference"],
        },
        description=proposal["description"],
        tags=("diversity", "teacher", "novelty_aware"),
        limits={
            "max_program_lines": config.max_program_lines,
            "max_program_characters": config.max_program_characters,
            "max_string_length": config.max_string_length,
        },
        concepts=tuple(dict.fromkeys(concepts)),
        task_domain=proposal["task_domain"],
        algorithm_family=proposal["algorithm_family"],
        composition_depth=min(3, max(1, len(proposal.get("operation_sequence", [])))),
        required_features=tuple(proposal["required_features"]),
        description_style=proposal["description_style"],
        source_type="teacher",
    )
    seen = {problem.behavior_signature for problem in existing_problems}
    problem = build_problem(
        rng,
        generated,
        ProblemBuildConfig(
            public_test_count=public_count,
            hidden_test_count=hidden_count,
            input_pool=InputPoolConfig(
                pool_size=domain_size,
                exhaustive_max_length=maximum,
            ),
            min_terminating_fraction=1.0,
            max_identity_fraction=0.999999,
            max_constant_fraction=0.999999,
        ),
        seen_signatures=seen,
    )
    return problem, score_novelty(problem, existing_problems)
