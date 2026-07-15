"""Task IR, Python oracle, and a deliberately bounded reliable compiler."""

import itertools
import json
from dataclasses import dataclass

from A2B import parse

from .dataset import execute_with_limits
from .generation import FailureReason, GeneratedProgram, GenerationRejected


SUPPORTED_OPERATIONS = {
    "map",
    "delete",
    "replace_substring",
    "normalize_runs",
    "reverse",
    "rotate",
    "move_symbols",
    "recognize_pattern",
    "finite_state_transduction",
    "unary_operation",
    "binary_operation",
    "encode",
    "decode",
    "compose",
}

COMPILABLE_PER_CHARACTER = {"map", "delete", "encode", "decode"}
ISOLATED_STAGE_OPERATIONS = COMPILABLE_PER_CHARACTER | {"reverse", "rotate"}
MARKER_POOL = tuple("XYZWVUQPKJHGFEDCBA9876543210!@$%^&*|?~")


@dataclass(frozen=True)
class IROperation:
    kind: str
    parameters: dict

    def __post_init__(self):
        if self.kind not in SUPPORTED_OPERATIONS:
            raise ValueError("unsupported IR operation: %s" % self.kind)
        if not isinstance(self.parameters, dict):
            raise TypeError("IR parameters must be an object")

    def to_dict(self):
        parameters = {}
        for key, value in self.parameters.items():
            if key == "operations":
                parameters[key] = [operation.to_dict() for operation in value]
            else:
                parameters[key] = value
        return {"kind": self.kind, "parameters": parameters}


@dataclass(frozen=True)
class TaskIR:
    operations: tuple
    input_alphabet: tuple

    def __post_init__(self):
        if not 1 <= len(self.operations) <= 3:
            raise ValueError("TaskIR supports composition depth 1 through 3")
        if not all(isinstance(operation, IROperation) for operation in self.operations):
            raise TypeError("operations must contain IROperation values")
        if not 1 <= len(self.input_alphabet) <= 4:
            raise ValueError("input alphabet must contain 1 through 4 symbols")
        if not all(isinstance(char, str) and len(char) == 1 for char in self.input_alphabet):
            raise ValueError("input alphabet entries must be single characters")

    @property
    def composition_depth(self):
        return len(self.operations)

    def apply(self, value):
        result = value
        for operation in self.operations:
            result = apply_operation(operation, result)
        return result

    def to_dict(self):
        return {
            "operations": [operation.to_dict() for operation in self.operations],
            "input_alphabet": list(self.input_alphabet),
        }


def _normalize_runs(value, symbols):
    if not value:
        return value
    output = [value[0]]
    for char in value[1:]:
        if char == output[-1] and char in symbols:
            continue
        output.append(char)
    return "".join(output)


def _finite_state(operation, value):
    parameters = operation.parameters
    state = parameters["start_state"]
    output = []
    transitions = parameters["transitions"]
    outputs = parameters.get("outputs", {})
    for char in value:
        key = state + "\0" + char
        if key not in transitions:
            raise ValueError("incomplete finite-state transition table")
        if key in outputs:
            output.append(outputs[key])
        state = transitions[key]
    if parameters.get("mode") == "dfa":
        return "true" if state in parameters["accepting_states"] else "false"
    return "".join(output)


def apply_operation(operation, value):
    kind = operation.kind
    parameters = operation.parameters
    if kind in ("map", "encode", "decode"):
        mapping = parameters["mapping"]
        return "".join(mapping.get(char, char) for char in value)
    if kind == "delete":
        symbols = set(parameters["symbols"])
        return "".join(char for char in value if char not in symbols)
    if kind == "replace_substring":
        return value.replace(parameters["old"], parameters["new"])
    if kind == "normalize_runs":
        return _normalize_runs(value, set(parameters["symbols"]))
    if kind == "reverse":
        return value[::-1]
    if kind == "rotate":
        if not value:
            return value
        amount = parameters.get("amount", 1) % len(value)
        direction = parameters.get("direction", "left")
        if direction == "right":
            amount = -amount
        return value[amount:] + value[:amount]
    if kind == "move_symbols":
        order = {char: index for index, char in enumerate(parameters["order"])}
        return "".join(sorted(value, key=lambda char: order[char]))
    if kind == "recognize_pattern":
        found = parameters["pattern"] in value
        return parameters.get("accept", "true") if found else parameters.get("reject", "false")
    if kind == "finite_state_transduction":
        return _finite_state(operation, value)
    if kind == "unary_operation":
        symbol = parameters.get("symbol", "a")
        amount = len(value)
        name = parameters["operation"]
        if name == "increment":
            amount += 1
        elif name == "decrement":
            amount = max(0, amount - 1)
        elif name == "double":
            amount *= 2
        elif name == "parity":
            return "odd" if amount % 2 else "even"
        elif name == "binary_increment":
            return bin(int(value, 2) + 1)[2:]
        else:
            raise ValueError("unsupported unary operation oracle: %s" % name)
        return symbol * amount
    if kind == "binary_operation":
        separator = parameters["separator"]
        left, right = value.split(separator, 1)
        name = parameters["operation"]
        representation = parameters.get("representation", "unary")
        if name == "concat":
            return left + right
        if representation == "unary":
            symbol = parameters.get("symbol", "a")
            left_value, right_value = len(left), len(right)
            if name == "add":
                result = left_value + right_value
            elif name == "subtract":
                result = max(0, left_value - right_value)
            else:
                raise ValueError("unsupported unary binary operation")
            return symbol * result
        left_value, right_value = int(left, 2), int(right, 2)
        if name == "xor":
            result = left_value ^ right_value
        elif name == "add":
            result = left_value + right_value
        else:
            raise ValueError("unsupported binary oracle operation")
        return bin(result)[2:]
    if kind == "compose":
        result = value
        for child in parameters["operations"]:
            result = apply_operation(child, result)
        return result
    raise AssertionError("unreachable IR operation")


def _choose_markers(rng, count, forbidden):
    available = [char for char in MARKER_POOL if char not in forbidden]
    if len(available) < count:
        raise GenerationRejected(FailureReason.RESOURCE_LIMIT, "not enough marker symbols")
    rng.shuffle(available)
    return tuple(available[:count])


def _mapping_for(operation, alphabet):
    if operation.kind in ("map", "encode", "decode"):
        mapping = operation.parameters["mapping"]
        return {char: mapping.get(char, char) for char in alphabet}
    if operation.kind == "delete":
        deleted = set(operation.parameters["symbols"])
        return {char: "" if char in deleted else char for char in alphabet}
    raise ValueError("not a per-character operation")


def _compile_per_character(ir, rng):
    forbidden = set(ir.input_alphabet)
    for operation in ir.operations:
        mapping = operation.parameters.get("mapping", {})
        forbidden.update("".join(mapping.values()))
    markers = _choose_markers(rng, len(ir.operations), forbidden)
    rules = ["(once)=(start)%s" % markers[0]]
    current_alphabet = tuple(ir.input_alphabet)
    for index, operation in enumerate(ir.operations):
        marker = markers[index]
        mapping = _mapping_for(operation, current_alphabet)
        for char in current_alphabet:
            rules.append("%s%s=%s%s" % (marker, char, mapping[char], marker))
        output_alphabet = []
        for value in mapping.values():
            for char in value:
                if char not in output_alphabet:
                    output_alphabet.append(char)
        if index + 1 < len(ir.operations):
            rules.append("(end)%s=(start)%s" % (marker, markers[index + 1]))
            current_alphabet = tuple(output_alphabet)
        else:
            rules.append("(end)%s=" % marker)
    return "\n".join(rules), markers, ("once", "start", "end", "marker_rewrite")


def _stage_output_alphabet(operation, alphabet):
    if operation.kind in COMPILABLE_PER_CHARACTER:
        mapping = _mapping_for(operation, alphabet)
        result = []
        for char in alphabet:
            for output in mapping[char]:
                if output not in result:
                    result.append(output)
        return tuple(result)
    return tuple(alphabet)


def _compile_isolated_stages(ir, rng, max_input_length):
    """Concatenate marker-gated stages whose rules cannot leak across phases."""
    sources = []
    markers = []
    features = []
    alphabet = tuple(ir.input_alphabet)
    for operation in ir.operations:
        if operation.kind not in ISOLATED_STAGE_OPERATIONS:
            raise NotImplementedError(
                "isolated composition does not support %s" % operation.kind
            )
        for _ in range(64):
            source, stage_markers, stage_features = compile_ir(
                TaskIR((operation,), alphabet),
                rng,
                max_input_length=max_input_length,
            )
            if not (set(stage_markers) & set(markers)):
                break
        else:
            raise GenerationRejected(
                FailureReason.RESOURCE_LIMIT,
                "could not allocate disjoint stage markers",
            )
        sources.append(source)
        markers.extend(stage_markers)
        features.extend(stage_features)
        alphabet = _stage_output_alphabet(operation, alphabet)
    return (
        "\n".join(sources),
        tuple(markers),
        tuple(dict.fromkeys(features + ["phase_boundary", "marker_isolation"])),
    )


def compile_ir(ir, rng, *, max_input_length):
    """Compile the reliable subset; unsupported combinations fail explicitly."""
    operations = ir.operations
    if all(operation.kind in COMPILABLE_PER_CHARACTER for operation in operations):
        return _compile_per_character(ir, rng)
    if len(operations) > 1:
        return _compile_isolated_stages(ir, rng, max_input_length)
    if len(operations) != 1:
        raise NotImplementedError(
            "composition currently compiles only map/delete/encode/decode stages"
        )
    operation = operations[0]
    kind = operation.kind
    parameters = operation.parameters
    markers = ()
    features = ["plain_rewrite"]

    if kind == "replace_substring":
        old, new = parameters["old"], parameters["new"]
        if not old or old in new:
            raise NotImplementedError("replacement must be terminating by construction")
        source = "%s=%s" % (old, new)
    elif kind == "normalize_runs":
        source = "\n".join("%s%s=%s" % (char, char, char) for char in parameters["symbols"])
    elif kind == "reverse":
        marker = _choose_markers(rng, 1, ir.input_alphabet)[0]
        markers = (marker,)
        rules = ["(once)=(end)%s" % (marker * max_input_length)]
        rules.extend("%s%s=(end)%s" % (char, marker, char) for char in ir.input_alphabet)
        rules.append("%s=" % marker)
        source = "\n".join(rules)
        features = ["once", "end", "marker_rewrite"]
    elif kind == "rotate" and parameters.get("amount", 1) == 1 and parameters.get("direction", "left") == "left":
        marker = _choose_markers(rng, 1, ir.input_alphabet)[0]
        markers = (marker,)
        rules = ["(once)=(start)%s" % marker]
        rules.extend("%s%s=(end)%s" % (marker, char, char) for char in ir.input_alphabet)
        rules.append("%s=" % marker)
        source = "\n".join(rules)
        features = ["once", "start", "end", "marker_rewrite"]
    elif kind == "move_symbols":
        order = parameters["order"]
        rules = []
        for high_index in range(1, len(order)):
            for low_index in range(high_index):
                rules.append("%s%s=%s%s" % (order[high_index], order[low_index], order[low_index], order[high_index]))
        source = "\n".join(rules)
    elif kind == "recognize_pattern":
        source = "%s=(return)%s\n=(return)%s" % (
            parameters["pattern"],
            parameters.get("accept", "true"),
            parameters.get("reject", "false"),
        )
        features = ["return", "empty_pattern"]
    elif kind == "finite_state_transduction":
        states = parameters["states"]
        marker_map = dict(zip(states, _choose_markers(rng, len(states), ir.input_alphabet)))
        markers = tuple(marker_map[state] for state in states)
        rules = ["(once)=(start)%s" % marker_map[parameters["start_state"]]]
        for state in states:
            for char in ir.input_alphabet:
                key = state + "\0" + char
                target = marker_map[parameters["transitions"][key]]
                output = parameters.get("outputs", {}).get(key, "")
                rules.append("%s%s=%s%s" % (marker_map[state], char, output, target))
        for state in states:
            marker = marker_map[state]
            if parameters["mode"] == "dfa":
                result = "true" if state in parameters["accepting_states"] else "false"
                rules.append("(end)%s=(return)%s" % (marker, result))
            else:
                rules.append("(end)%s=" % marker)
        source = "\n".join(rules)
        features = ["once", "start", "end", "return" if parameters["mode"] == "dfa" else "marker_rewrite"]
    elif kind == "unary_operation":
        name = parameters["operation"]
        symbol = parameters.get("symbol", "a")
        if name == "increment":
            source = "(once)=(end)%s" % symbol
            features = ["once", "end", "empty_pattern"]
        elif name == "decrement":
            source = "(once)%s=" % symbol
            features = ["once"]
        elif name == "double":
            operation = IROperation("map", {"mapping": {symbol: symbol * 2}})
            return _compile_per_character(TaskIR((operation,), ir.input_alphabet), rng)
        elif name == "binary_increment":
            marker = _choose_markers(rng, 1, ir.input_alphabet)[0]
            markers = (marker,)
            source = "\n".join(
                (
                    "(once)=(end)%s" % marker,
                    "0%s=1" % marker,
                    "1%s=%s0" % (marker, marker),
                    "%s=1" % marker,
                )
            )
            features = ["once", "end", "marker_rewrite"]
        else:
            raise NotImplementedError("unary compiler does not support %s" % name)
    elif kind == "binary_operation" and parameters["operation"] in ("add", "concat"):
        source = "%s=" % parameters["separator"]
    else:
        raise NotImplementedError("compiler does not support %s" % kind)
    return source, markers, tuple(features)


CONCEPTS = {
    "map": ("character_mapping", "substitution"),
    "delete": ("deletion", "filtering"),
    "replace_substring": ("substring_replacement", "local_rewrite"),
    "normalize_runs": ("run_normalization", "idempotence"),
    "reverse": ("reversal", "symbol_movement"),
    "rotate": ("rotation", "symbol_movement"),
    "move_symbols": ("sorting", "permutation", "rule_order"),
    "recognize_pattern": ("pattern_recognition", "classification"),
    "finite_state_transduction": ("finite_state_machine", "state_transition"),
    "unary_operation": ("unary_arithmetic",),
    "binary_operation": ("binary_operation",),
    "encode": ("encoding", "character_mapping"),
    "decode": ("decoding", "character_mapping"),
    "compose": ("composition", "staged_computation"),
}


DOMAIN_BY_KIND = {
    "map": "string_normalization",
    "delete": "string_normalization",
    "replace_substring": "rewrite_systems",
    "normalize_runs": "string_normalization",
    "reverse": "movement_permutation",
    "rotate": "movement_permutation",
    "move_symbols": "movement_permutation",
    "recognize_pattern": "pattern_recognition",
    "finite_state_transduction": "finite_state_machines",
    "unary_operation": "unary_arithmetic",
    "binary_operation": "binary_operations",
    "encode": "encoding_decoding",
    "decode": "encoding_decoding",
}


def ir_concepts(ir):
    concepts = []
    if len(ir.operations) > 1:
        concepts.extend(("composition", "staged_computation", "marker_isolation"))
    for operation in ir.operations:
        name = operation.parameters.get("operation")
        if operation.kind == "unary_operation" and name == "binary_increment":
            concepts.extend(("binary_arithmetic", "binary_representation", "carry_propagation"))
        else:
            concepts.extend(CONCEPTS[operation.kind])
        if operation.kind == "binary_operation":
            concepts.extend(("binary_arithmetic", "binary_representation"))
        if name:
            concepts.append(name)
        if operation.kind == "finite_state_transduction":
            concepts.append("accept_reject" if operation.parameters["mode"] == "dfa" else "transduction")
    return tuple(dict.fromkeys(concepts))


def _symbol_list(symbols):
    return "、".join("`%s`" % symbol for symbol in symbols)


def _input_specification(ir, minimum_input_length, maximum_input_length):
    operation = ir.operations[0]
    if operation.kind == "binary_operation":
        separator = operation.parameters["separator"]
        return "两个操作数，中间用 `%s` 分隔" % separator
    if (
        operation.kind == "unary_operation"
        and operation.parameters["operation"] == "binary_increment"
    ):
        base = "一个不含前导零的二进制数"
    else:
        base = "一个仅由 %s 组成的字符串" % _symbol_list(ir.input_alphabet)
    if maximum_input_length is None:
        return base
    if minimum_input_length == 0:
        return "%s，可以为空，长度不超过 %d" % (base, maximum_input_length)
    return "%s，长度为 %d 到 %d" % (
        base,
        minimum_input_length,
        maximum_input_length,
    )


def _operation_specification(operation):
    p = operation.parameters
    if operation.kind in ("map", "encode", "decode"):
        changes = [
            "将 `%s` 替换为 `%s`" % (source, target)
            for source, target in sorted(p["mapping"].items())
            if source != target
        ]
        unchanged = [
            source
            for source, target in sorted(p["mapping"].items())
            if source == target
        ]
        result = (
            "同时" + "，".join(changes)
            if changes
            else "保持字符串不变"
        )
        if unchanged:
            result += "；%s 保持不变" % _symbol_list(unchanged)
        return result
    if operation.kind == "delete":
        return "删除所有 %s" % _symbol_list(sorted(p["symbols"]))
    if operation.kind == "replace_substring":
        return "从左到右将每个互不重叠的 `%s` 替换为 `%s`" % (
            p["old"],
            p["new"],
        )
    if operation.kind == "normalize_runs":
        return (
            "对于 %s，将每段连续的相同字符缩短为一个字符；其他字符保持不变"
            % _symbol_list(sorted(p["symbols"]))
        )
    if operation.kind == "reverse":
        return "反转字符串"
    if operation.kind == "rotate":
        return "将字符串循环%s移 %d 位" % (
            "右" if p.get("direction", "left") == "right" else "左",
            p.get("amount", 1),
        )
    if operation.kind == "move_symbols":
        return "将字符按照 %s 的顺序稳定排序" % " < ".join(
            "`%s`" % char for char in p["order"]
        )
    if operation.kind == "recognize_pattern":
        return "如果字符串包含 `%s`，输出 `%s`；否则输出 `%s`" % (
            p["pattern"],
            p.get("accept", "true"),
            p.get("reject", "false"),
        )
    if operation.kind == "finite_state_transduction":
        rows = []
        for key, target in sorted(p["transitions"].items()):
            state, char = key.split("\0", 1)
            if p["mode"] == "fst":
                rows.append(
                    "`%s` 读到 `%s` 时输出 `%s` 并转到 `%s`"
                    % (state, char, p["outputs"][key], target)
                )
            else:
                rows.append(
                    "`%s` 读到 `%s` 时转到 `%s`" % (state, char, target)
                )
        prefix = "从状态 `%s` 开始，从左到右读取输入。" % p["start_state"]
        if p["mode"] == "dfa":
            suffix = "读完后处于 %s 时输出 `true`，否则输出 `false`" % _symbol_list(
                sorted(p["accepting_states"])
            )
        else:
            suffix = "输出所有转移产生的字符连接而成的字符串"
        return prefix + " ".join(row + "。" for row in rows) + suffix
    if operation.kind == "unary_operation":
        name = p["operation"]
        symbol = p.get("symbol", "a")
        if name == "increment":
            return "在字符串末尾添加一个 `%s`" % symbol
        if name == "decrement":
            return "删除最靠左的一个 `%s`；没有 `%s` 时输出空字符串" % (
                symbol,
                symbol,
            )
        if name == "double":
            return "将字符串长度加倍"
        if name == "parity":
            return "长度为奇数时输出 `odd`，否则输出 `even`"
        if name == "binary_increment":
            return "输出该二进制数加 1 后的二进制表示"
    if operation.kind == "binary_operation":
        name = p["operation"]
        if name == "concat":
            return "删除分隔符并连接两个操作数"
        return "输出两个操作数进行 %s 后的结果" % name
    raise ValueError("cannot describe IR operation %s" % operation.kind)


def describe_ir(
    ir,
    style,
    *,
    minimum_input_length=0,
    maximum_input_length=None,
):
    input_text = _input_specification(
        ir, minimum_input_length, maximum_input_length
    )
    operations = [_operation_specification(operation) for operation in ir.operations]
    if len(operations) == 1:
        output_text = operations[0]
    else:
        links = ["先" + operations[0]]
        links.extend("再" + operation for operation in operations[1:])
        output_text = "；".join(links)
    if style == "io_only":
        return "此候选缺少唯一的自然语言输出规格，不得用于程序合成数据。"
    if style == "table":
        return "输入：%s。\n输出：%s。" % (input_text, output_text)
    if style == "narrative":
        return "给定%s，%s。" % (input_text, output_text)
    return "%s。%s。" % (input_text, output_text)


def generated_from_ir(
    ir,
    rng,
    config,
    *,
    source_type,
    description_style,
    algorithm_family=None,
    task_domain=None,
    max_input_length=None,
):
    maximum_input = (
        config.max_string_length if max_input_length is None else max_input_length
    )
    minimum_input = 0
    if any(
        operation.kind == "unary_operation"
        and operation.parameters.get("operation") in ("increment", "double", "binary_increment")
        for operation in ir.operations
    ):
        maximum_input = min(maximum_input, max(1, config.max_string_length // 2))
        if any(
            operation.kind == "unary_operation"
            and operation.parameters.get("operation") == "binary_increment"
            for operation in ir.operations
        ):
            minimum_input = 1
    source, markers, features = compile_ir(
        ir, rng, max_input_length=maximum_input
    )
    lines = source.splitlines()
    if len(lines) > config.max_program_lines:
        raise GenerationRejected(
            FailureReason.RESOURCE_LIMIT,
            "compiled program exceeds max_program_lines",
        )
    if len(source) > config.max_program_characters:
        raise GenerationRejected(
            FailureReason.RESOURCE_LIMIT,
            "compiled program exceeds max_program_characters",
        )
    domain = task_domain or (
        "marker_rewrite"
        if len(ir.operations) > 1
        else DOMAIN_BY_KIND[ir.operations[0].kind]
    )
    family = algorithm_family or "+".join(operation.kind for operation in ir.operations)
    return GeneratedProgram(
        program=source,
        template_family="ir_" + family,
        template_version="1.0.0",
        generator_name="ir_compiler",
        generator_version="1.0.0",
        difficulty=min(5, 1 + ir.composition_depth + len(lines) // 8),
        allowed_features=tuple(features),
        parameters={
            "ir": ir.to_dict(),
            "operation_sequence": [operation.kind for operation in ir.operations],
            "input_alphabet": list(ir.input_alphabet),
            "min_input_length": minimum_input,
            "max_input_length": maximum_input,
            "marker_allocation": list(markers),
            **(
                {"forbid_leading_zero": True}
                if any(
                    operation.kind == "unary_operation"
                    and operation.parameters.get("operation") == "binary_increment"
                    for operation in ir.operations
                )
                else {}
            ),
        },
        description=describe_ir(
            ir,
            description_style,
            minimum_input_length=minimum_input,
            maximum_input_length=maximum_input,
        ),
        tags=("diversity", "ir", "depth_%d" % ir.composition_depth),
        limits={
            "max_program_lines": config.max_program_lines,
            "max_program_characters": config.max_program_characters,
            "max_string_length": config.max_string_length,
        },
        concepts=tuple(
            dict.fromkeys(
                ir_concepts(ir)
                + (
                    (
                        "bitwise_operation",
                        "binary_not"
                        if family == "binary_not"
                        else "bit_reversal"
                        if family == "binary_reverse"
                        else "bit_run_normalization"
                        if family == "binary_run_normalizer"
                        else "binary_arithmetic",
                    )
                    if domain == "binary_operations"
                    else ()
                )
            )
        ),
        task_domain=domain,
        algorithm_family=family,
        composition_depth=ir.composition_depth,
        required_features=tuple(features),
        description_style=description_style,
        source_type=source_type,
    )


def exhaustive_inputs(alphabet, minimum, maximum):
    for length in range(minimum, maximum + 1):
        for chars in itertools.product(alphabet, repeat=length):
            yield "".join(chars)


def verify_ir_oracle(ir, generated, *, maximum_length, max_steps=10000):
    program = parse(generated.program)
    minimum = generated.parameters.get("min_input_length", 0)
    for value in exhaustive_inputs(ir.input_alphabet, minimum, maximum_length):
        if (
            generated.parameters.get("forbid_leading_zero")
            and len(value) > 1
            and value.startswith("0")
        ):
            continue
        expected = ir.apply(value)
        outcome = execute_with_limits(
            program,
            value,
            max_steps=max_steps,
            max_length=generated.limits["max_string_length"],
        )
        if not outcome.terminating or outcome.output != expected:
            raise GenerationRejected(
                FailureReason.VERIFIER_FAILURE,
                "IR mismatch on %r: expected %r, got %r"
                % (value, expected, outcome.output),
            )
    return True
