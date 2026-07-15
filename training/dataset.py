"""Verified problem construction, quality metrics, signatures, and dedup."""

import hashlib
import itertools
import json
import random
from collections import Counter
from dataclasses import asdict, dataclass, field

from A2B import EXECUTED_DONE, EXECUTED_NONE, EXECUTED_RETURN, parse

from .generation import (
    FailureReason,
    GeneratedProgram,
    GenerationConfig,
    GenerationRejected,
    GenerationStats,
    TemplateCatalog,
)
from .fingerprints import semantic_fingerprint, structural_fingerprint


HARDENING_TASK_FIELDS = {
    "declared_composition_depth",
    "effective_composition_depth",
    "effective_components",
    "dead_components",
    "component_interaction",
    "order_sensitive",
    "order_distinguishing_input",
    "order_comparison",
    "order_outputs",
    "reducible_to_single_stage",
    "normalized_semantic_ir",
    "genuine_composition",
    "superficial_composition",
    "specification_level",
    "solution_revealing_score",
    "concrete_behavior_fingerprint",
    "alpha_normalized_behavior_fingerprint",
    "semantic_ir_fingerprint",
    "ontology_errors",
    "root_problem_id",
    "program_lineage_id",
    "mutant_family_id",
    "alpha_equivalence_class",
    "construction_domain",
    "public_domain",
    "hidden_domain",
    "generalization_domain",
    "audit_domain",
    "audit_reference_verification",
    "cognitive_family",
    "semantic_archetype",
    "parameter_instance",
    "information_scope",
    "memory_model",
    "traversal_model",
    "output_shape",
    "primary_invariant",
    "cognitive_signature",
    "composition_component_probe",
}


@dataclass(frozen=True)
class InputPoolConfig:
    pool_size: int = 96
    exhaustive_max_length: int = 3

    def __post_init__(self):
        for name in ("pool_size", "exhaustive_max_length"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("%s must be a non-negative integer" % name)


@dataclass(frozen=True)
class ProblemBuildConfig:
    public_test_count: int = 8
    hidden_test_count: int = 32
    input_pool: InputPoolConfig = field(default_factory=InputPoolConfig)
    max_execution_steps: int = 10000
    min_terminating_fraction: float = 1.0
    max_identity_fraction: float = 1.0
    max_constant_fraction: float = 1.0

    def __post_init__(self):
        for name in ("public_test_count", "hidden_test_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("%s must be a positive integer" % name)
        if (
            isinstance(self.max_execution_steps, bool)
            or not isinstance(self.max_execution_steps, int)
            or self.max_execution_steps <= 0
        ):
            raise ValueError("max_execution_steps must be a positive integer")
        for name in (
            "min_terminating_fraction",
            "max_identity_fraction",
            "max_constant_fraction",
        ):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError("%s must be between 0 and 1" % name)


@dataclass(frozen=True)
class ExecutionOutcome:
    input: str
    output: str = None
    steps: int = 0
    terminating: bool = False
    error: str = None


@dataclass(frozen=True)
class QualityMetrics:
    identity_fraction: float
    constant_fraction: float
    terminating_fraction: float
    program_lines: int
    execution_steps: tuple
    distinct_outputs: int
    public_hidden_overlap: int = 0


@dataclass(frozen=True)
class GeneratedProblem:
    id: str
    generated_program: GeneratedProgram
    public_tests: tuple
    hidden_tests: tuple
    behavior_signature: str
    semantic_fingerprint: str
    structural_fingerprint: str
    quality: QualityMetrics
    hardening: dict = field(default_factory=dict)

    def to_task_record(self):
        generated = self.generated_program
        quality = asdict(self.quality)
        quality["execution_steps"] = list(quality["execution_steps"])
        record = {
            "id": self.id,
            "description": generated.description,
            "public_tests": [dict(case) for case in self.public_tests],
            "hidden_tests": [dict(case) for case in self.hidden_tests],
            "reference_programs": [generated.program],
            "metadata": {
                "generator_name": generated.generator_name,
                "generator_version": generated.generator_version,
                "template_version": generated.template_version,
                "difficulty": generated.difficulty,
                "allowed_features": list(generated.allowed_features),
                "parameters": generated.parameters,
                "tags": list(generated.tags),
                "quality": quality,
            },
            "limits": dict(generated.limits),
            "generator": {
                "name": generated.generator_name,
                "version": generated.generator_version,
            },
            "template_family": generated.template_family,
            "behavior_signature": self.behavior_signature,
            "concepts": list(generated.concepts),
            "task_domain": generated.task_domain,
            "algorithm_family": generated.algorithm_family,
            "composition_depth": generated.composition_depth,
            "required_features": list(generated.required_features),
            "description_style": generated.description_style,
            "source_type": generated.source_type,
            "semantic_fingerprint": self.semantic_fingerprint,
            "structural_fingerprint": self.structural_fingerprint,
        }
        record.update(self.hardening)
        return record

    @staticmethod
    def from_task_record(record):
        metadata = record["metadata"]
        quality_data = dict(metadata["quality"])
        quality_data["execution_steps"] = tuple(quality_data["execution_steps"])
        generated = GeneratedProgram(
            program=record["reference_programs"][0],
            template_family=record["template_family"],
            template_version=metadata["template_version"],
            generator_name=metadata["generator_name"],
            generator_version=metadata["generator_version"],
            difficulty=metadata["difficulty"],
            allowed_features=tuple(metadata["allowed_features"]),
            parameters=dict(metadata["parameters"]),
            description=record["description"],
            tags=tuple(metadata["tags"]),
            limits=dict(record["limits"]),
            concepts=tuple(record["concepts"]),
            task_domain=record["task_domain"],
            algorithm_family=record["algorithm_family"],
            composition_depth=record["composition_depth"],
            required_features=tuple(record["required_features"]),
            description_style=record["description_style"],
            source_type=record["source_type"],
        )
        return GeneratedProblem(
            id=record["id"],
            generated_program=generated,
            public_tests=tuple(dict(case) for case in record["public_tests"]),
            hidden_tests=tuple(dict(case) for case in record["hidden_tests"]),
            behavior_signature=record["behavior_signature"],
            semantic_fingerprint=record["semantic_fingerprint"],
            structural_fingerprint=record["structural_fingerprint"],
            quality=QualityMetrics(**quality_data),
            hardening={
                key: record[key]
                for key in HARDENING_TASK_FIELDS
                if key in record
            },
        )


@dataclass(frozen=True)
class DatasetGenerationResult:
    problems: tuple
    stats: GenerationStats
    requested: int


def execute_with_limits(program, input_value, *, max_steps, max_length):
    """Execute a parsed program and return termination/step information."""
    for expression in program.exprs:
        expression.executed = 0

    line = input_value
    steps = 0
    if len(line) > max_length:
        return ExecutionOutcome(
            input=input_value,
            steps=steps,
            terminating=False,
            error="input_length_limit",
        )

    while True:
        executed = EXECUTED_NONE
        for expression in program.exprs:
            executed, output = expression.Execute(line)
            if executed in (EXECUTED_DONE, EXECUTED_RETURN):
                steps += 1
                line = output
                break
        else:
            return ExecutionOutcome(
                input=input_value,
                output=line,
                steps=steps,
                terminating=True,
            )

        if steps > max_steps:
            return ExecutionOutcome(
                input=input_value,
                steps=steps,
                terminating=False,
                error="execution_step_limit",
            )
        if len(line) > max_length:
            return ExecutionOutcome(
                input=input_value,
                steps=steps,
                terminating=False,
                error="string_length_limit",
            )
        if executed == EXECUTED_RETURN:
            return ExecutionOutcome(
                input=input_value,
                output=line,
                steps=steps,
                terminating=True,
            )


def _input_spec(generated):
    parameters = generated.parameters
    alphabet = parameters.get("input_alphabet", ["a", "b", "c"])
    if not isinstance(alphabet, (list, tuple)) or not alphabet:
        raise GenerationRejected(
            FailureReason.VERIFIER_FAILURE, "input_alphabet must be non-empty"
        )
    if not all(isinstance(char, str) and len(char) == 1 for char in alphabet):
        raise GenerationRejected(
            FailureReason.VERIFIER_FAILURE,
            "input_alphabet entries must be single characters",
        )
    minimum = parameters.get("min_input_length", 0)
    maximum = parameters.get(
        "max_input_length", generated.limits.get("max_string_length", 8)
    )
    maximum = min(maximum, generated.limits.get("max_string_length", maximum))
    if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum < 0:
        raise GenerationRejected(FailureReason.VERIFIER_FAILURE, "invalid input length")
    if maximum < minimum:
        raise GenerationRejected(FailureReason.VERIFIER_FAILURE, "empty input domain")
    return tuple(alphabet), minimum, maximum, bool(
        parameters.get("forbid_leading_zero", False)
    )


def _valid_input(value, forbid_leading_zero):
    return not (
        forbid_leading_zero and len(value) > 1 and value.startswith("0")
    )


def build_input_pool(rng, generated, config):
    """Build a deterministic boundary-plus-random pool from program metadata."""
    alphabet, minimum, maximum, forbid_leading_zero = _input_spec(generated)
    values = []
    seen = set()

    exhaustive_maximum = min(maximum, config.exhaustive_max_length)
    for length in range(minimum, exhaustive_maximum + 1):
        for chars in itertools.product(alphabet, repeat=length):
            value = "".join(chars)
            if _valid_input(value, forbid_leading_zero) and value not in seen:
                seen.add(value)
                values.append(value)

    # Deterministic structural boundaries that random sampling is unlikely to hit.
    if maximum >= max(1, minimum):
        for char in alphabet:
            value = char * maximum
            if _valid_input(value, forbid_leading_zero) and value not in seen:
                seen.add(value)
                values.append(value)
    if maximum >= 3 and minimum <= 3 and len(alphabet) > 1:
        for char in alphabet:
            other = next(value for value in alphabet if value != char)
            for value in (char + other + other, other + other + char, other + char + other):
                if _valid_input(value, forbid_leading_zero) and value not in seen:
                    seen.add(value)
                    values.append(value)

    target = config.pool_size
    attempts = 0
    attempt_limit = max(100, target * 50)
    while len(values) < target and attempts < attempt_limit:
        attempts += 1
        length = rng.randint(minimum, maximum)
        value = "".join(alphabet[rng.randrange(len(alphabet))] for _ in range(length))
        if _valid_input(value, forbid_leading_zero) and value not in seen:
            seen.add(value)
            values.append(value)

    if len(values) < target:
        # Finite small domains may legitimately contain fewer than pool_size.
        domain_size = sum(len(alphabet) ** length for length in range(minimum, maximum + 1))
        if domain_size > len(values):
            for length in range(exhaustive_maximum + 1, maximum + 1):
                for chars in itertools.product(alphabet, repeat=length):
                    value = "".join(chars)
                    if _valid_input(value, forbid_leading_zero) and value not in seen:
                        seen.add(value)
                        values.append(value)
                        if len(values) >= target:
                            break
                if len(values) >= target:
                    break
    return tuple(values[:target])


def evaluate_inputs(generated, inputs, config):
    program = parse(generated.program)
    return tuple(
        execute_with_limits(
            program,
            value,
            max_steps=config.max_execution_steps,
            max_length=generated.limits["max_string_length"],
        )
        for value in inputs
    )


def _case(outcome):
    return {"input": outcome.input, "output": outcome.output}


def _simple_hypothesis_mismatches(outcomes):
    """Return mismatch sets for cheap programs public tests should rule out."""
    alphabet = sorted({char for outcome in outcomes for char in outcome.input})
    outputs = sorted({outcome.output for outcome in outcomes})
    sources = [""]
    for output in outputs:
        sources.append("=(return)%s" % output)
    for char in alphabet:
        sources.extend(("%s=" % char, "(start)%s=" % char, "(end)%s=" % char))
        sources.append("(start)%s=\n(end)%s=" % (char, char))
        for count in range(1, 5):
            sources.append("\n".join("(once)%s=" % char for _ in range(count)))
        for target in alphabet:
            if target != char:
                sources.append("%s=%s" % (char, target))
        sources.append("%s=(return)true\n=(return)false" % char)
    for marker in ("X", "Y", "Z"):
        sources.append(
            "\n".join(
                (
                    "(once)=(end)%s" % marker,
                    "0%s=1" % marker,
                    "1%s=%s0" % (marker, marker),
                    "%s=1" % marker,
                )
            )
        )

    reference = {outcome.input: outcome.output for outcome in outcomes}
    max_length = max(
        [len(value) for value in reference] + [len(value) for value in reference.values()] + [1]
    ) + 32
    mismatches = []
    for source in sources:
        try:
            program = parse(source)
        except Exception:
            continue
        wrong = set()
        for outcome in outcomes:
            candidate = execute_with_limits(
                program,
                outcome.input,
                max_steps=1000,
                max_length=max_length,
            )
            if not candidate.terminating or candidate.output != outcome.output:
                wrong.add(outcome.input)
        if wrong and len(wrong) < len(outcomes):
            mismatches.append(wrong)
    return mismatches


def select_public_hidden(rng, outcomes, public_count, hidden_count):
    terminating = [outcome for outcome in outcomes if outcome.terminating]
    required = public_count + hidden_count
    if len(terminating) < required:
        reason = (
            FailureReason.INSUFFICIENT_PUBLIC_TESTS
            if len(terminating) < public_count
            else FailureReason.INSUFFICIENT_HIDDEN_TESTS
        )
        raise GenerationRejected(
            reason,
            "need %d terminating cases, found %d" % (required, len(terminating)),
        )

    shuffled = list(terminating)
    rng.shuffle(shuffled)
    # Stable boundary preference after shuffle keeps variety within equal groups.
    shuffled.sort(key=lambda item: (item.input != "", len(item.input)))

    public = []
    remaining = list(shuffled)

    def take_first(predicate):
        if len(public) >= public_count:
            return
        index = next(
            (i for i, item in enumerate(remaining) if predicate(item)),
            None,
        )
        if index is not None:
            public.append(remaining.pop(index))

    # Greedily eliminate cheap wrong hypotheses before adding general boundaries.
    wrong_hypotheses = _simple_hypothesis_mismatches(terminating)
    while wrong_hypotheses and remaining and len(public) < public_count:
        best = max(
            remaining,
            key=lambda item: sum(
                item.input in mismatches for mismatches in wrong_hypotheses
            ),
        )
        score = sum(best.input in mismatches for mismatches in wrong_hypotheses)
        if score == 0:
            break
        take_first(lambda item, value=best.input: item.input == value)
        wrong_hypotheses = [
            mismatches
            for mismatches in wrong_hypotheses
            if best.input not in mismatches
        ]

    # Cover each observed one-character input; this exposes per-symbol mappings.
    singleton_inputs = sorted(
        {item.input for item in remaining if len(item.input) == 1}
    )
    for singleton in singleton_inputs:
        take_first(lambda item, value=singleton: item.input == value)
    # Repeated-symbol probes distinguish bounded/once behavior from one-rule fits.
    for singleton in singleton_inputs:
        repetitions = [
            item.input
            for item in remaining
            if len(item.input) > 1 and set(item.input) == {singleton}
        ]
        if repetitions:
            repeated = max(repetitions, key=len)
            take_first(lambda item, value=repeated: item.input == value)
    # Preserve explicit empty-input and maximum-length boundaries when slots allow.
    take_first(lambda item: item.input == "")
    if remaining:
        maximum_length = max(len(item.input) for item in remaining)
        take_first(lambda item: len(item.input) == maximum_length)
    # Make simple identity shortcuts observable even for unusual input domains.
    take_first(lambda item: item.output != item.input)
    take_first(lambda item: item.output == item.input)

    seen_outputs = set()
    seen_outputs.update(item.output for item in public)
    while remaining and len(public) < public_count:
        index = next(
            (
                i
                for i, item in enumerate(remaining)
                if item.output not in seen_outputs
            ),
            0,
        )
        selected = remaining.pop(index)
        public.append(selected)
        seen_outputs.add(selected.output)

    rng.shuffle(remaining)
    hidden = remaining[:hidden_count]
    return tuple(_case(item) for item in public), tuple(_case(item) for item in hidden)


def behavior_signature(outcomes):
    payload = [
        {
            "input": outcome.input,
            "output": outcome.output,
            "terminating": outcome.terminating,
            "error": outcome.error,
        }
        for outcome in sorted(outcomes, key=lambda item: (len(item.input), item.input))
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def quality_metrics(generated, outcomes, public_tests=(), hidden_tests=()):
    count = len(outcomes)
    terminating = [outcome for outcome in outcomes if outcome.terminating]
    identities = sum(
        outcome.output == outcome.input for outcome in terminating
    )
    outputs = Counter(outcome.output for outcome in terminating)
    public_inputs = {case["input"] for case in public_tests}
    hidden_inputs = {case["input"] for case in hidden_tests}
    return QualityMetrics(
        identity_fraction=(identities / len(terminating) if terminating else 0.0),
        constant_fraction=(max(outputs.values()) / len(terminating) if outputs else 0.0),
        terminating_fraction=(len(terminating) / count if count else 0.0),
        program_lines=len(generated.program.splitlines()),
        execution_steps=tuple(outcome.steps for outcome in outcomes),
        distinct_outputs=len(outputs),
        public_hidden_overlap=len(public_inputs & hidden_inputs),
    )


def build_problem(rng, generated, config, seen_signatures=None):
    inputs = build_input_pool(rng, generated, config.input_pool)
    outcomes = evaluate_inputs(generated, inputs, config)
    metrics = quality_metrics(generated, outcomes)
    if metrics.terminating_fraction < config.min_terminating_fraction:
        raise GenerationRejected(
            FailureReason.NO_TERMINATING_INPUTS,
            "terminating fraction %.6f is below %.6f"
            % (metrics.terminating_fraction, config.min_terminating_fraction),
        )
    if metrics.identity_fraction > config.max_identity_fraction:
        raise GenerationRejected(FailureReason.TRIVIAL_BEHAVIOR, "identity fraction")
    if metrics.constant_fraction > config.max_constant_fraction:
        raise GenerationRejected(FailureReason.TRIVIAL_BEHAVIOR, "constant fraction")

    # Signature probes must not depend on the sampling history of this attempt.
    signature_inputs = build_input_pool(
        random.Random(0), generated, config.input_pool
    )
    signature_outcomes = evaluate_inputs(generated, signature_inputs, config)
    signature = behavior_signature(signature_outcomes)
    alphabet = generated.parameters.get("input_alphabet", ())
    semantic = semantic_fingerprint(signature_outcomes, alphabet)
    structural = structural_fingerprint(generated.program, alphabet)
    if seen_signatures is not None and signature in seen_signatures:
        raise GenerationRejected(FailureReason.DUPLICATE_BEHAVIOR)

    public, hidden = select_public_hidden(
        rng,
        outcomes,
        config.public_test_count,
        config.hidden_test_count,
    )
    metrics = quality_metrics(generated, outcomes, public, hidden)
    if metrics.public_hidden_overlap:
        raise GenerationRejected(
            FailureReason.VERIFIER_FAILURE, "public/hidden input overlap"
        )

    problem_id = "%s-%s" % (generated.template_family, signature[:12])
    if seen_signatures is not None:
        seen_signatures.add(signature)
    return GeneratedProblem(
        id=problem_id,
        generated_program=generated,
        public_tests=public,
        hidden_tests=hidden,
        behavior_signature=signature,
        semantic_fingerprint=semantic,
        structural_fingerprint=structural,
        quality=metrics,
    )


def generate_dataset(
    catalog,
    *,
    seed,
    count,
    generation_config=None,
    build_config=None,
):
    """Generate a deduplicated dataset with a strict global attempt bound."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    if not isinstance(catalog, TemplateCatalog):
        raise TypeError("catalog must be TemplateCatalog")
    generation_config = generation_config or GenerationConfig()
    build_config = build_config or ProblemBuildConfig()
    rng = random.Random(seed)
    stats = GenerationStats()
    seen_signatures = set()
    problems = []
    max_total_attempts = count * generation_config.max_attempts

    while len(problems) < count and stats.attempts < max_total_attempts:
        try:
            generated = catalog.generate_attempt(rng, generation_config, stats=stats)
        except GenerationRejected:
            # TemplateCatalog records generation-stage rejections.
            continue
        try:
            problem = build_problem(
                rng, generated, build_config, seen_signatures=seen_signatures
            )
        except GenerationRejected as rejection:
            stats.reject(rejection.reason)
            continue
        problems.append(problem)

    return DatasetGenerationResult(
        problems=tuple(problems), stats=stats, requested=count
    )
