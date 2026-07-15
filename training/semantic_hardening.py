"""Semantic composition, specification, ontology, and domain audits."""

import hashlib
import itertools
import json
import random
from types import SimpleNamespace

from .fingerprints import semantic_fingerprint
from .ir import IROperation, TaskIR, apply_operation


PER_CHARACTER = {"map", "delete", "encode", "decode"}
SCALABLE_FAMILIES = {
    "random_dfa",
    "random_fst",
    "reversal",
    "binary_reverse",
    "symbol_sort",
    "run_normalizer",
    "binary_run_normalizer",
    "unary_increment",
    "unary_decrement",
    "binary_increment",
}


def _digest(value):
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _operation_mapping(operation, alphabet):
    if operation.kind in {"map", "encode", "decode"}:
        mapping = operation.parameters["mapping"]
        return {char: mapping.get(char, char) for char in alphabet}
    deleted = set(operation.parameters["symbols"])
    return {char: "" if char in deleted else char for char in alphabet}


def _canonicalize_ir_payload(operations, input_alphabet):
    symbol_names = {char: "I%d" % index for index, char in enumerate(input_alphabet)}
    state_names = {}

    def symbol(value):
        result = []
        for char in value:
            if char not in symbol_names:
                symbol_names[char] = "O%d" % (
                    len(symbol_names) - len(input_alphabet)
                )
            result.append(symbol_names[char])
        return result

    def state(value):
        if value not in state_names:
            state_names[value] = "S%d" % len(state_names)
        return state_names[value]

    normalized = []
    for operation in operations:
        kind = operation["kind"]
        parameters = operation.get("parameters", {})
        item = {"kind": kind, "parameters": {}}
        if "mapping" in parameters:
            item["parameters"]["mapping"] = [
                [symbol(source), symbol(target)]
                for source, target in sorted(parameters["mapping"].items())
            ]
        if "symbols" in parameters:
            item["parameters"]["symbols"] = sorted(
                (symbol(value) for value in parameters["symbols"]),
                key=str,
            )
        for name in ("old", "new", "pattern", "separator", "symbol"):
            if name in parameters:
                item["parameters"][name] = symbol(parameters[name])
        for name in ("amount", "direction", "mode", "operation", "representation"):
            if name in parameters:
                item["parameters"][name] = parameters[name]
        if "states" in parameters:
            item["parameters"]["states"] = [state(value) for value in parameters["states"]]
            item["parameters"]["start_state"] = state(parameters["start_state"])
            item["parameters"]["accepting_states"] = sorted(
                state(value) for value in parameters.get("accepting_states", [])
            )
            transitions = []
            for key, target in sorted(parameters["transitions"].items()):
                source_state, char = key.split("\0", 1)
                row = [state(source_state), symbol(char), state(target)]
                if key in parameters.get("outputs", {}):
                    row.append(symbol(parameters["outputs"][key]))
                transitions.append(row)
            item["parameters"]["transitions"] = transitions
        normalized.append(item)
    return normalized


def normalized_semantic_ir(ir):
    """Fold only semantics-preserving, explicitly understood operation chains."""
    result = []
    alphabet = tuple(ir.input_alphabet)
    index = 0
    while index < len(ir.operations):
        operation = ir.operations[index]
        if operation.kind in PER_CHARACTER:
            mapping = {char: char for char in alphabet}
            while index < len(ir.operations) and ir.operations[index].kind in PER_CHARACTER:
                stage = _operation_mapping(ir.operations[index], tuple(mapping.values()))
                mapping = {
                    source: "".join(stage.get(char, char) for char in output)
                    for source, output in mapping.items()
                }
                index += 1
            result.append({"kind": "per_character_map", "parameters": {"mapping": mapping}})
            alphabet = tuple(dict.fromkeys("".join(mapping.values())))
            continue
        if operation.kind == "reverse" and result and result[-1]["kind"] == "reverse":
            result.pop()
        else:
            result.append(operation.to_dict())
        index += 1
    canonical = _canonicalize_ir_payload(result, ir.input_alphabet)
    return {
        "input_alphabet_size": len(ir.input_alphabet),
        "operations": canonical,
    }


def semantic_ir_fingerprint(ir):
    return _digest(normalized_semantic_ir(ir))


def _targeted_inputs(alphabet, minimum, maximum, *, cap=768, seed=0):
    values = []
    seen = set()

    def add(value):
        if minimum <= len(value) <= maximum and value not in seen:
            seen.add(value)
            values.append(value)

    exhaustive_maximum = min(maximum, 4)
    for length in range(minimum, exhaustive_maximum + 1):
        for chars in itertools.product(alphabet, repeat=length):
            add("".join(chars))
            if len(values) >= cap:
                return tuple(values)
    for length in sorted({maximum, max(minimum, maximum - 1), max(minimum, 5), max(minimum, 6)}):
        for char in alphabet:
            add(char * length)
        if len(alphabet) > 1:
            add("".join(alphabet[index % len(alphabet)] for index in range(length)))
            add("".join(reversed(alphabet))[0] * max(0, length - 1) + alphabet[0])
    rng = random.Random(seed)
    attempts = 0
    while len(values) < cap and attempts < cap * 20:
        attempts += 1
        length = rng.randint(minimum, maximum)
        add("".join(alphabet[rng.randrange(len(alphabet))] for _ in range(length)))
    return tuple(values)


def audit_domain_for_problem(problem):
    generated = problem.generated_program
    parameters = generated.parameters
    minimum = parameters.get("min_input_length", 0)
    construction_maximum = parameters.get("construction_max_input_length", parameters.get("max_input_length", 3))
    family = generated.algorithm_family
    scalable = (
        family in SCALABLE_FAMILIES
        or generated.composition_depth > 1
        or generated.task_domain in {"finite_state_machines", "unary_arithmetic", "binary_operations"}
    )
    generalization_maximum = min(
        parameters.get("max_input_length", generated.limits["max_string_length"]),
        max(construction_maximum, 8 if scalable else construction_maximum),
    )
    public_lengths = [len(case["input"]) for case in problem.public_tests]
    hidden_lengths = [len(case["input"]) for case in problem.hidden_tests]
    return {
        "construction_domain": {"min_length": minimum, "max_length": construction_maximum},
        "public_domain": {
            "min_length": min(public_lengths),
            "max_length": max(public_lengths),
        },
        "hidden_domain": {
            "min_length": min(hidden_lengths),
            "max_length": max(hidden_lengths),
        },
        "generalization_domain": {
            "min_length": minimum,
            "max_length": generalization_maximum,
        },
        "audit_domain": {
            "min_length": minimum,
            "max_length": generalization_maximum,
            "probe_cap": 768,
        },
    }


def composition_analysis(ir, inputs):
    full = [ir.apply(value) for value in inputs]
    effective = []
    dead = []
    for index in range(len(ir.operations)):
        remaining = ir.operations[:index] + ir.operations[index + 1 :]
        reduced = []
        for value in inputs:
            output = value
            for operation in remaining:
                output = apply_operation(operation, output)
            reduced.append(output)
        (effective if reduced != full else dead).append(index)

    permutations = []
    if len(ir.operations) > 1:
        permutations.append(tuple(reversed(ir.operations)))
        for index in range(len(ir.operations) - 1):
            swapped = list(ir.operations)
            swapped[index], swapped[index + 1] = swapped[index + 1], swapped[index]
            permutations.append(tuple(swapped))
    order_sensitive = False
    distinguishing_input = None
    order_comparison = None
    order_outputs = None
    for candidate in permutations:
        for value, expected in zip(inputs, full):
            output = value
            for operation in candidate:
                output = apply_operation(operation, output)
            if output != expected:
                order_sensitive = True
                distinguishing_input = value
                order_comparison = [operation.kind for operation in candidate]
                order_outputs = {"declared": expected, "comparison": output}
                break
        if order_sensitive:
            break

    normalized = normalized_semantic_ir(ir)
    normalized_depth = len(normalized["operations"])
    reducible = len(ir.operations) > 1 and normalized_depth <= 1
    if dead:
        interaction = "dead_component"
    elif reducible:
        interaction = "effective_but_reducible"
    elif order_sensitive:
        interaction = "genuine_order_sensitive"
    else:
        interaction = "genuine_commuting"
    return {
        "declared_composition_depth": len(ir.operations),
        "effective_composition_depth": len(effective),
        "effective_components": effective,
        "dead_components": dead,
        "component_interaction": interaction,
        "order_sensitive": order_sensitive,
        "order_distinguishing_input": distinguishing_input,
        "order_comparison": order_comparison,
        "order_outputs": order_outputs,
        "reducible_to_single_stage": reducible,
        "normalized_semantic_ir": normalized,
        "genuine_composition": not dead and not reducible and len(ir.operations) >= 2,
        "superficial_composition": bool(dead or reducible),
    }


def specification_analysis(generated):
    if generated.description_style == "io_only":
        level = "io_only"
        score = 0.0
    elif generated.source_type == "random_mined" or "规则按优先级" in generated.description:
        level = "operational"
        line_count = len(generated.program.splitlines())
        score = min(1.0, 0.65 + line_count * 0.1)
    else:
        level = "functional"
        score = 0.25
        if generated.composition_depth > 1:
            score += 0.1
        if "转移" in generated.description:
            score += 0.15
    return {
        "specification_level": level,
        "solution_revealing_score": round(min(score, 1.0), 6),
    }


def ontology_errors(generated):
    concepts = set(generated.concepts)
    errors = []
    family = generated.algorithm_family
    if family == "binary_increment" and "unary_arithmetic" in concepts:
        errors.append("binary_increment_mislabeled_unary")
    if family.startswith("binary_") and not (
        {"binary_arithmetic", "bitwise_operation", "binary_representation"} & concepts
    ):
        errors.append("binary_family_missing_binary_concept")
    if generated.composition_depth > 1 and "composition" not in concepts:
        errors.append("composition_missing_concept")
    if generated.task_domain == "finite_state_machines" and "finite_state_machine" not in concepts:
        errors.append("fsm_domain_missing_concept")
    return tuple(errors)


def analyze_problem(problem):
    generated = problem.generated_program
    ir_data = generated.parameters.get("ir")
    if not ir_data:
        normalized = {
            "input_alphabet_size": len(generated.parameters.get("input_alphabet", ())),
            "operations": [
                {
                    "kind": "opaque_program",
                    "parameters": {
                        "structural_fingerprint": problem.structural_fingerprint
                    },
                }
            ],
        }
        composition = {
            "declared_composition_depth": generated.composition_depth,
            "effective_composition_depth": 1,
            "effective_components": [0],
            "dead_components": [],
            "component_interaction": "not_composed",
            "order_sensitive": False,
            "order_distinguishing_input": None,
            "order_comparison": None,
            "order_outputs": None,
            "reducible_to_single_stage": False,
            "normalized_semantic_ir": normalized,
            "genuine_composition": False,
            "superficial_composition": False,
        }
        concrete_behavior = problem.behavior_signature
        alpha_behavior = problem.semantic_fingerprint
    else:
        operations = tuple(
            IROperation(item["kind"], item["parameters"])
            for item in ir_data["operations"]
        )
        ir = TaskIR(operations, tuple(ir_data["input_alphabet"]))
        domains = audit_domain_for_problem(problem)
        audit = domains["audit_domain"]
        inputs = _targeted_inputs(
            ir.input_alphabet,
            audit["min_length"],
            audit["max_length"],
            cap=audit["probe_cap"],
            seed=int(problem.behavior_signature[:12], 16),
        )
        composition = composition_analysis(ir, inputs)
        oracle_outcomes = [
            SimpleNamespace(
                input=value,
                output=ir.apply(value),
                terminating=True,
                error=None,
            )
            for value in inputs
        ]
        concrete_behavior = _digest(
            [
                {"input": outcome.input, "output": outcome.output}
                for outcome in oracle_outcomes
            ]
        )
        alpha_behavior = semantic_fingerprint(
            oracle_outcomes, ir.input_alphabet
        )
    domains = audit_domain_for_problem(problem)
    specification = specification_analysis(generated)
    semantic_ir = _digest(composition["normalized_semantic_ir"])
    return {
        **composition,
        **specification,
        **domains,
        "concrete_behavior_fingerprint": concrete_behavior,
        "alpha_normalized_behavior_fingerprint": alpha_behavior,
        "structural_fingerprint": problem.structural_fingerprint,
        "semantic_ir_fingerprint": semantic_ir,
        "ontology_errors": list(ontology_errors(generated)),
    }
