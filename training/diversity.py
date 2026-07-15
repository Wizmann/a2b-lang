"""用于多样性实验的 IR、有限状态机与程序挖掘生成器。"""

import random
from collections import Counter
from dataclasses import dataclass

from .dataset import (
    DatasetGenerationResult,
    InputPoolConfig,
    ProblemBuildConfig,
    build_problem,
)
from .generation import (
    FailureReason,
    GenerationConfig,
    GenerationRejected,
    GenerationStats,
)
from .ir import (
    IROperation,
    TaskIR,
    generated_from_ir,
    verify_ir_oracle,
)
from .mining import mine_programs


ALPHABETS = (
    ("a", "b"),
    ("a", "b", "c"),
    ("d", "e", "f"),
    ("g", "h", "i", "j"),
    ("k", "l", "m"),
    ("p", "q"),
)
ENCODING_ALPHABETS = (
    ("u", "v", "w", "x"),
    ("r", "s", "t", "y"),
)
DESCRIPTION_STYLES = ("direct", "narrative", "table")
FORBIDDEN_DESCRIPTION_PHRASES = (
    "根据公开样例",
    "根据公开输入输出样例",
    "小型文本机器",
    "操作顺序",
    "依次删除字符集合",
    "步骤 1",
)


def _validate_description(description):
    if not isinstance(description, str) or not description.strip():
        raise GenerationRejected(
            FailureReason.AMBIGUOUS_DESCRIPTION,
            "description is empty",
        )
    for phrase in FORBIDDEN_DESCRIPTION_PHRASES:
        if phrase in description:
            raise GenerationRejected(
                FailureReason.AMBIGUOUS_DESCRIPTION,
                "description contains meta or ambiguous wording: %s" % phrase,
            )


@dataclass(frozen=True)
class DiversityConfig:
    count: int = 240
    seed: int = 20260715
    max_attempts_per_problem: int = 40
    max_program_lines: int = 32
    max_program_characters: int = 512
    max_string_length: int = 12
    construction_max_input_length: int = 3
    generalization_max_input_length: int = None
    mined_fraction: float = 0.3
    max_structural_cluster_size: int = 3

    def __post_init__(self):
        if not 200 <= self.count <= 500:
            raise ValueError("diversity smoke count must be between 200 and 500")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if not 0.25 <= self.mined_fraction <= 0.5:
            raise ValueError("mined_fraction must be between 0.25 and 0.5")
        if self.max_structural_cluster_size < 2:
            raise ValueError("max_structural_cluster_size must be at least 2")
        if self.construction_max_input_length < 1:
            raise ValueError("construction_max_input_length must be positive")
        if (
            self.generalization_max_input_length is not None
            and self.generalization_max_input_length
            < self.construction_max_input_length
        ):
            raise ValueError(
                "generalization_max_input_length must cover construction"
            )


def _alphabet(rng, minimum=2, maximum=4):
    choices = [value for value in ALPHABETS if minimum <= len(value) <= maximum]
    return tuple(choices[rng.randrange(len(choices))])


def _non_identity_mapping(rng, alphabet):
    mapping = {}
    changed = False
    for char in alphabet:
        target = alphabet[rng.randrange(len(alphabet))]
        mapping[char] = target
        changed |= target != char
    if not changed:
        mapping[alphabet[0]] = alphabet[-1]
    return mapping


def _random_fsm(rng, mode):
    alphabet = _alphabet(rng, 2, 4)
    state_count = rng.randint(2, 5)
    states = tuple("q%d" % index for index in range(state_count))
    transitions = {}
    outputs = {}
    output_alphabet = ("u", "v", "w")
    for state in states:
        for char in alphabet:
            key = state + "\0" + char
            transitions[key] = states[rng.randrange(state_count)]
            if mode == "fst":
                outputs[key] = output_alphabet[rng.randrange(len(output_alphabet))]
    accepting_count = rng.randint(1, state_count - 1)
    accepting = list(states)
    rng.shuffle(accepting)
    parameters = {
        "mode": mode,
        "states": list(states),
        "start_state": states[0],
        "transitions": transitions,
        "accepting_states": sorted(accepting[:accepting_count]),
    }
    if mode == "fst":
        parameters["outputs"] = outputs
    return TaskIR((IROperation("finite_state_transduction", parameters),), alphabet)


def _composition(rng, depth):
    alphabet = _alphabet(rng, 2, 4)
    if rng.randrange(2) == 0:
        movement = [
            IROperation("reverse", {}),
            IROperation("rotate", {"amount": 1, "direction": "left"}),
        ]
        if depth == 2:
            if rng.randrange(2):
                movement.reverse()
            return TaskIR(tuple(movement), alphabet)
        mapping = IROperation(
            "map", {"mapping": _non_identity_mapping(rng, alphabet)}
        )
        operations = [mapping] + movement
        rng.shuffle(operations)
        return TaskIR(tuple(operations), alphabet)
    operations = []
    for index in range(depth):
        selector = rng.randrange(3)
        if selector == 0:
            operations.append(
                IROperation("map", {"mapping": _non_identity_mapping(rng, alphabet)})
            )
        elif selector == 1:
            symbol = alphabet[rng.randrange(len(alphabet))]
            operations.append(IROperation("delete", {"symbols": [symbol]}))
        else:
            # A bijection keeps later stage alphabets well-defined.
            targets = list(alphabet)
            rng.shuffle(targets)
            if tuple(targets) == alphabet:
                targets = targets[1:] + targets[:1]
            operations.append(
                IROperation("encode", {"mapping": dict(zip(alphabet, targets))})
            )
    return TaskIR(tuple(operations), alphabet)


def _recipe(rng, recipe_index):
    kind = recipe_index % 15
    style = DESCRIPTION_STYLES[rng.randrange(len(DESCRIPTION_STYLES))]
    if kind == 0:
        alphabet = _alphabet(rng)
        ir = TaskIR((IROperation("map", {"mapping": _non_identity_mapping(rng, alphabet)}),), alphabet)
        return ir, "template", style, "character_map", None
    if kind == 1:
        alphabet = _alphabet(rng)
        symbols = list(alphabet)
        rng.shuffle(symbols)
        ir = TaskIR((IROperation("delete", {"symbols": symbols[: rng.randint(1, len(symbols) - 1)]}),), alphabet)
        return ir, "enumerated", style, "symbol_filter", None
    if kind == 2:
        alphabet = _alphabet(rng)
        ir = TaskIR((IROperation("normalize_runs", {"symbols": list(alphabet)}),), alphabet)
        return ir, "template", style, "run_normalizer", None
    if kind == 3:
        alphabet = _alphabet(rng)
        old = alphabet[rng.randrange(len(alphabet))] * rng.randint(1, 2)
        targets = [char for char in alphabet if char not in old]
        new = targets[rng.randrange(len(targets))] if targets else ""
        ir = TaskIR((IROperation("replace_substring", {"old": old, "new": new}),), alphabet)
        return ir, "enumerated", style, "substring_rewriter", None
    if kind == 4:
        alphabet = _alphabet(rng)
        return TaskIR((IROperation("reverse", {}),), alphabet), "handwritten", style, "reversal", None
    if kind == 5:
        alphabet = _alphabet(rng)
        operation = IROperation("rotate", {"amount": 1, "direction": "left"})
        return TaskIR((operation,), alphabet), "handwritten", style, "rotate_left", None
    if kind == 6:
        alphabet = list(_alphabet(rng))
        rng.shuffle(alphabet)
        operation = IROperation("move_symbols", {"order": alphabet})
        return TaskIR((operation,), tuple(sorted(alphabet))), "handwritten", style, "symbol_sort", None
    if kind == 7:
        alphabet = _alphabet(rng)
        pattern = "".join(alphabet[rng.randrange(len(alphabet))] for _ in range(rng.randint(1, 3)))
        operation = IROperation("recognize_pattern", {"pattern": pattern, "accept": "true", "reject": "false"})
        return TaskIR((operation,), alphabet), "template", style, "substring_classifier", None
    if kind == 8:
        symbol = ("a", "d", "k", "p")[rng.randrange(4)]
        alphabet = (symbol,)
        name = ("increment", "decrement", "double")[rng.randrange(3)]
        operation = IROperation("unary_operation", {"operation": name, "symbol": symbol})
        return TaskIR((operation,), alphabet), "enumerated", style, "unary_" + name, None
    if kind == 9:
        variant = rng.randrange(4)
        if variant == 0:
            operation = IROperation("unary_operation", {"operation": "binary_increment"})
            family = "binary_increment"
        elif variant == 1:
            operation = IROperation("map", {"mapping": {"0": "1", "1": "0"}})
            family = "binary_not"
        elif variant == 2:
            operation = IROperation("reverse", {})
            family = "binary_reverse"
        else:
            operation = IROperation("normalize_runs", {"symbols": ["0", "1"]})
            family = "binary_run_normalizer"
        return TaskIR((operation,), ("0", "1")), "handwritten", style, family, "binary_operations"
    if kind == 10:
        alphabet = _alphabet(rng, 2, 3)
        encoded = ENCODING_ALPHABETS[rng.randrange(len(ENCODING_ALPHABETS))][: len(alphabet)]
        if rng.randrange(2):
            mapping = dict(zip(alphabet, encoded))
            operation = IROperation("encode", {"mapping": mapping})
            return TaskIR((operation,), alphabet), "enumerated", style, "symbol_encoder", None
        mapping = dict(zip(encoded, alphabet))
        operation = IROperation("decode", {"mapping": mapping})
        return TaskIR((operation,), encoded), "enumerated", style, "symbol_decoder", None
    if kind == 11:
        return _composition(rng, 2), "composed", style, None, "marker_rewrite"
    if kind == 12:
        return _composition(rng, 3), "composed", style, None, "marker_rewrite"
    if kind == 13:
        return _random_fsm(rng, "dfa"), "enumerated", style, "random_dfa", "finite_state_machines"
    return _random_fsm(rng, "fst"), "enumerated", style, "random_fst", "finite_state_machines"


def _domain_maximum(generated):
    alphabet_size = len(generated.parameters["input_alphabet"])
    if alphabet_size == 1:
        return generated.parameters["max_input_length"]
    if alphabet_size == 2:
        return min(generated.parameters["max_input_length"], 5)
    return min(generated.parameters["max_input_length"], 3)


def _build_config_for(generated):
    maximum = _domain_maximum(generated)
    alphabet_size = len(generated.parameters["input_alphabet"])
    minimum = generated.parameters.get("min_input_length", 0)
    domain_size = sum(alphabet_size ** length for length in range(minimum, maximum + 1))
    if generated.parameters.get("forbid_leading_zero"):
        domain_size = alphabet_size + sum(
            (alphabet_size - 1) * alphabet_size ** (length - 1)
            for length in range(max(2, minimum), maximum + 1)
        )
    public = min(12, max(2, domain_size // 4))
    hidden = min(48, domain_size - public)
    if hidden <= 0:
        raise GenerationRejected(FailureReason.INSUFFICIENT_HIDDEN_TESTS)
    return ProblemBuildConfig(
        public_test_count=public,
        hidden_test_count=hidden,
        input_pool=InputPoolConfig(
            pool_size=max(domain_size, 96),
            exhaustive_max_length=maximum,
        ),
        max_execution_steps=2000,
        min_terminating_fraction=1.0,
        max_identity_fraction=0.999999,
        max_constant_fraction=0.999999,
    )


def _build_ir_problem(rng, ir, generated, seen):
    maximum = _domain_maximum(generated)
    verify_ir_oracle(ir, generated, maximum_length=maximum, max_steps=2000)
    return build_problem(
        rng,
        generated,
        _build_config_for(generated),
        seen_signatures=seen,
    )


def _build_mined_problem(rng, generated, seen):
    return build_problem(
        rng,
        generated,
        _build_config_for(generated),
        seen_signatures=seen,
    )


def generate_diversity_smoke(config=None):
    config = config or DiversityConfig()
    rng = random.Random(config.seed)
    generation_config = GenerationConfig(
        max_attempts=config.max_attempts_per_problem,
        max_program_lines=config.max_program_lines,
        max_program_characters=config.max_program_characters,
        max_string_length=config.max_string_length,
    )
    stats = GenerationStats()
    seen = set()
    structural_counts = Counter()
    problems = []
    mined_target = round(config.count * config.mined_fraction)
    ir_target = config.count - mined_target
    attempt_limit = ir_target * config.max_attempts_per_problem
    recipe_index = 0

    def requested_input_maximum(ir):
        if config.generalization_max_input_length is not None:
            return config.generalization_max_input_length
        return (
            config.max_string_length
            if len(ir.input_alphabet) == 1
            else 5
            if len(ir.input_alphabet) == 2
            else 3
        )

    while len(problems) < ir_target and stats.attempts < attempt_limit:
        stats.attempts += 1
        ir, source_type, style, family, domain = _recipe(rng, recipe_index)
        recipe_index += 1
        try:
            generated = generated_from_ir(
                ir,
                rng,
                generation_config,
                source_type=source_type,
                description_style=style,
                algorithm_family=family,
                task_domain=domain,
                max_input_length=requested_input_maximum(ir),
            )
            generated.parameters["construction_max_input_length"] = min(
                config.construction_max_input_length,
                generated.parameters["max_input_length"],
            )
            _validate_description(generated.description)
            problem = _build_ir_problem(rng, ir, generated, seen)
            if structural_counts[problem.structural_fingerprint] >= config.max_structural_cluster_size:
                raise GenerationRejected(
                    FailureReason.DUPLICATE_STRUCTURE,
                    "structural cluster size limit",
                )
        except (GenerationRejected, NotImplementedError) as error:
            reason = (
                error.reason
                if isinstance(error, GenerationRejected)
                else FailureReason.VERIFIER_FAILURE
            )
            stats.reject(reason)
            continue
        stats.successes += 1
        stats.selected_templates[generated.algorithm_family] += 1
        structural_counts[problem.structural_fingerprint] += 1
        problems.append(problem)

    mined = mine_programs(
        seed=config.seed + 1,
        limit=mined_target * 4,
        config=generation_config,
    )
    for generated in mined:
        if len(problems) >= config.count:
            break
        stats.attempts += 1
        try:
            _validate_description(generated.description)
            problem = _build_mined_problem(rng, generated, seen)
            if structural_counts[problem.structural_fingerprint] >= config.max_structural_cluster_size:
                raise GenerationRejected(
                    FailureReason.DUPLICATE_STRUCTURE,
                    "structural cluster size limit",
                )
        except GenerationRejected as error:
            stats.reject(error.reason)
            continue
        stats.successes += 1
        stats.selected_templates[generated.algorithm_family] += 1
        structural_counts[problem.structural_fingerprint] += 1
        problems.append(problem)

    # If mining yielded fewer unique tasks, fill with additional balanced IR tasks.
    fill_limit = config.count * config.max_attempts_per_problem
    while len(problems) < config.count and stats.attempts < fill_limit:
        stats.attempts += 1
        ir, source_type, style, family, domain = _recipe(rng, recipe_index)
        recipe_index += 1
        try:
            generated = generated_from_ir(
                ir,
                rng,
                generation_config,
                source_type=source_type,
                description_style=style,
                algorithm_family=family,
                task_domain=domain,
                max_input_length=requested_input_maximum(ir),
            )
            generated.parameters["construction_max_input_length"] = min(
                config.construction_max_input_length,
                generated.parameters["max_input_length"],
            )
            _validate_description(generated.description)
            problem = _build_ir_problem(rng, ir, generated, seen)
            if structural_counts[problem.structural_fingerprint] >= config.max_structural_cluster_size:
                raise GenerationRejected(
                    FailureReason.DUPLICATE_STRUCTURE,
                    "structural cluster size limit",
                )
        except (GenerationRejected, NotImplementedError) as error:
            reason = error.reason if isinstance(error, GenerationRejected) else FailureReason.VERIFIER_FAILURE
            stats.reject(reason)
            continue
        stats.successes += 1
        stats.selected_templates[generated.algorithm_family] += 1
        structural_counts[problem.structural_fingerprint] += 1
        problems.append(problem)

    return DatasetGenerationResult(
        problems=tuple(problems), stats=stats, requested=config.count
    )


def diversity_distributions(problems):
    fields = {
        "task_domain": Counter(),
        "source_type": Counter(),
        "algorithm_family": Counter(),
        "composition_depth": Counter(),
        "description_style": Counter(),
        "concepts": Counter(),
        "template_family": Counter(),
    }
    joint = Counter()
    for problem in problems:
        generated = problem.generated_program
        fields["task_domain"][generated.task_domain] += 1
        fields["source_type"][generated.source_type] += 1
        fields["algorithm_family"][generated.algorithm_family] += 1
        fields["composition_depth"][generated.composition_depth] += 1
        fields["description_style"][generated.description_style] += 1
        fields["template_family"][generated.template_family] += 1
        fields["concepts"].update(generated.concepts)
        joint[(generated.task_domain, generated.source_type, generated.composition_depth)] += 1
    result = {name: dict(values) for name, values in fields.items()}
    result["joint_domain_source_depth"] = {
        "|".join(map(str, key)): value for key, value in joint.items()
    }
    return result
