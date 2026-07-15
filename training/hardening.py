"""语义加固生成与参考验证。"""

import random
from collections import Counter
from dataclasses import dataclass, replace

from A2B import parse

from .dataset import DatasetGenerationResult, execute_with_limits
from .diversity import DiversityConfig, generate_diversity_smoke
from .generation import GenerationStats
from .ir import IROperation, TaskIR
from .schema import validate_hardened_task
from .semantic_hardening import (
    _targeted_inputs,
    analyze_problem,
)


@dataclass(frozen=True)
class HardeningConfig:
    count: int = 240
    seed: int = 20260715
    candidate_count: int = 360
    construction_max_input_length: int = 3
    generalization_max_input_length: int = 8
    max_program_lines: int = 32
    max_program_characters: int = 512
    max_runtime_string_length: int = 24

    def __post_init__(self):
        if not 240 <= self.count <= 500:
            raise ValueError("hardening smoke count must be between 240 and 500")
        if not self.count <= self.candidate_count <= 500:
            raise ValueError("candidate_count must be between count and 500")
        if self.generalization_max_input_length <= self.construction_max_input_length:
            raise ValueError("generalization domain must exceed construction domain")


@dataclass(frozen=True)
class HardeningGenerationResult:
    problems: tuple
    stats: GenerationStats
    requested: int
    rejected: dict


def _ir_from_problem(problem):
    value = problem.generated_program.parameters.get("ir")
    if not value:
        return None
    return TaskIR(
        tuple(
            IROperation(item["kind"], item["parameters"])
            for item in value["operations"]
        ),
        tuple(value["input_alphabet"]),
    )


def verify_reference_on_audit_domain(problem, analysis):
    ir = _ir_from_problem(problem)
    if ir is None:
        return {"attempted": 0, "verified": 0, "fraction": 1.0}
    audit = analysis["audit_domain"]
    inputs = _targeted_inputs(
        ir.input_alphabet,
        audit["min_length"],
        audit["max_length"],
        cap=audit["probe_cap"],
        seed=int(problem.behavior_signature[:12], 16),
    )
    program = parse(problem.generated_program.program)
    verified = 0
    for value in inputs:
        result = execute_with_limits(
            program,
            value,
            max_steps=10000,
            max_length=problem.generated_program.limits["max_string_length"],
        )
        if result.terminating and result.output == ir.apply(value):
            verified += 1
    return {
        "attempted": len(inputs),
        "verified": verified,
        "fraction": verified / len(inputs) if inputs else 1.0,
    }


def _lineage(problem, analysis):
    return {
        "root_problem_id": problem.id,
        "program_lineage_id": "program:" + analysis["concrete_behavior_fingerprint"],
        "mutant_family_id": "mutant:" + problem.id,
        "alpha_equivalence_class": problem.structural_fingerprint,
    }


def harden_problem(problem):
    analysis = analyze_problem(problem)
    verification = verify_reference_on_audit_domain(problem, analysis)
    hardening = {
        **analysis,
        **_lineage(problem, analysis),
        "audit_reference_verification": verification,
    }
    hardened = replace(problem, hardening=hardening)
    validate_hardened_task(hardened.to_task_record())
    return hardened


def _valid_formal_composition(problem):
    data = problem.hardening
    if problem.generated_program.composition_depth == 1:
        return True
    if data["effective_composition_depth"] < 2:
        return False
    if (
        problem.generated_program.composition_depth == 3
        and len(data["effective_components"]) != 3
    ):
        return False
    return True


def generate_hardening_smoke(config=None):
    config = config or HardeningConfig()
    base = generate_diversity_smoke(
        DiversityConfig(
            count=config.candidate_count,
            seed=config.seed,
            max_attempts_per_problem=40,
            max_program_lines=config.max_program_lines,
            max_program_characters=config.max_program_characters,
            max_string_length=config.max_runtime_string_length,
            construction_max_input_length=config.construction_max_input_length,
            generalization_max_input_length=config.generalization_max_input_length,
            mined_fraction=0.30,
            max_structural_cluster_size=3,
        )
    )
    rejected = Counter()
    accepted = []
    seen_concrete_behaviors = set()
    for problem in base.problems:
        hardened = harden_problem(problem)
        if hardened.hardening["ontology_errors"]:
            rejected["ontology_error"] += 1
            continue
        if not _valid_formal_composition(hardened):
            rejected["ineffective_composition"] += 1
            continue
        if hardened.hardening["audit_reference_verification"]["fraction"] != 1.0:
            rejected["long_domain_verifier_failure"] += 1
            continue
        fingerprint = hardened.hardening["concrete_behavior_fingerprint"]
        if fingerprint in seen_concrete_behaviors:
            rejected["duplicate_audit_behavior"] += 1
            continue
        seen_concrete_behaviors.add(fingerprint)
        accepted.append(hardened)

    rng = random.Random(config.seed + 9001)
    rng.shuffle(accepted)
    selected = accepted[: config.count]
    if len(selected) < config.count:
        raise RuntimeError(
            "hardening produced %d valid tasks, need %d"
            % (len(selected), config.count)
        )
    depths = Counter(
        problem.generated_program.composition_depth for problem in selected
    )
    if not all(depths[depth] for depth in (1, 2, 3)):
        raise RuntimeError("hardening selection lost a composition depth")
    return HardeningGenerationResult(
        problems=tuple(selected),
        stats=base.stats,
        requested=config.count,
        rejected=dict(rejected),
    )
