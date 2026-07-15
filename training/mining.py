"""Bounded short-program mining with behavior clustering and property labels."""

import itertools
import random
from collections import defaultdict, deque

from A2B import A2BParseException, parse

from .dataset import behavior_signature, execute_with_limits
from .fingerprints import structural_fingerprint
from .generation import GeneratedProgram, GenerationConfig
from .ir import exhaustive_inputs


def describe_mined_program(source, alphabet=None, max_input_length=None):
    """Translate a supported mined program into exact rewrite rules."""
    descriptions = []
    for line in source.splitlines():
        if line.count("=") != 1:
            return None
        left, right = line.split("=", 1)
        modifier = None
        for prefix in ("once", "start", "end"):
            token = "(%s)" % prefix
            if left.startswith(token):
                modifier = prefix
                left = left[len(token) :]
                break

        if right.startswith("(return)"):
            output = right[len("(return)") :]
            condition = "总是" if not left else "若包含子串 %r" % left
            action = "%s，立即输出 %r 并停止" % (condition, output)
        else:
            replacement = "删除它" if not right else "替换为 %r" % right
            if modifier == "start":
                action = "若以 %r 开头，将该前缀%s" % (left, replacement)
            elif modifier == "end":
                action = "若以 %r 结尾，将该后缀%s" % (left, replacement)
            elif not left:
                action = "在最左侧空串位置插入 %r" % right
            else:
                action = "将最左侧出现的 %r %s" % (left, replacement)
            if modifier == "once":
                action += "，且整次运行最多执行一次"
        descriptions.append(action)

    if not descriptions:
        return None
    rules = "；".join(
        "%d. %s" % (index, description)
        for index, description in enumerate(descriptions, 1)
    )
    rule_text = (
        "规则按优先级为：%s。每次替换后重新从规则 1 检查；"
        "无规则可执行时输出当前字符串。" % rules
    )
    if alphabet is None:
        return rule_text
    symbols = "、".join("`%s`" % symbol for symbol in alphabet)
    return (
        "输入是一个仅由 %s 组成的字符串，可以为空，长度不超过 %d。%s"
        % (symbols, max_input_length, rule_text)
    )


def behavior_properties(source, alphabet, probe_inputs, outcomes):
    terminating = all(outcome.terminating for outcome in outcomes)
    outputs = [outcome.output for outcome in outcomes if outcome.terminating]
    program = parse(source)
    idempotent = terminating
    if idempotent:
        for output in outputs:
            second = execute_with_limits(
                program, output, max_steps=200, max_length=32
            )
            if not second.terminating or second.output != output:
                idempotent = False
                break
    lengths = [(len(value), len(output)) for value, output in zip(probe_inputs, outputs)]
    output_alphabet = set("".join(outputs))
    distinct_outputs = set(outputs)
    return {
        "idempotent": idempotent,
        "length_preserving": bool(lengths) and all(a == b for a, b in lengths),
        "length_increasing": any(b > a for a, b in lengths),
        "length_decreasing": any(b < a for a, b in lengths),
        "alphabet_preserving": output_alphabet <= set(alphabet),
        "possible_normalizer": idempotent and any(b < a for a, b in lengths),
        "possible_classifier": 1 < len(distinct_outputs) <= 4 and not output_alphabet <= set(alphabet),
        "possible_encoder": not output_alphabet <= set(alphabet) and len(distinct_outputs) > 4,
    }


def _candidate_rules(alphabet):
    rules = []
    for source in alphabet:
        for target in alphabet:
            if source != target:
                rules.append("%s=%s" % (source, target))
        rules.extend(
            (
                "%s=%s" % (source, source.upper()),
                "%s=" % source,
                "%s%s=%s" % (source, source, source),
                "(start)%s=" % source,
                "(end)%s=" % source,
                "(once)%s=" % source,
                "%s=(return)yes\n=(return)no" % source,
            )
        )
    for left, right in itertools.permutations(alphabet, 2):
        rules.append("%s%s=%s%s" % (left, right, right, left))
    return tuple(dict.fromkeys(rules))


def mine_programs(*, seed, limit, config=None, allow_io_only=False):
    """Return rare-cluster-first mined programs; never retries without a bound."""
    config = config or GenerationConfig(max_string_length=6)
    rng = random.Random(seed)
    alphabets = (("a", "b"), ("a", "b", "c"), ("d", "e"), ("g", "h", "i"))
    unique_behaviors = set()
    unique_structures = set()
    clusters = defaultdict(deque)

    for alphabet in alphabets:
        rules = list(_candidate_rules(alphabet))
        candidates = list(rules)
        # A bounded randomized sample of ordered two-rule programs.
        pairs = list(itertools.permutations(rules, 2))
        rng.shuffle(pairs)
        candidates.extend("\n".join(pair) for pair in pairs[:600])
        probes = tuple(exhaustive_inputs(alphabet, 0, 3))
        for source in candidates:
            if len(source.splitlines()) > min(2, config.max_program_lines):
                continue
            if len(source) > config.max_program_characters:
                continue
            try:
                program = parse(source)
            except A2BParseException:
                continue
            outcomes = tuple(
                execute_with_limits(
                    program,
                    value,
                    max_steps=100,
                    max_length=config.max_string_length,
                )
                for value in probes
            )
            if not all(outcome.terminating for outcome in outcomes):
                continue
            outputs = [outcome.output for outcome in outcomes]
            if all(output == value for value, output in zip(probes, outputs)):
                continue
            if len(set(outputs)) == 1:
                continue
            signature = behavior_signature(outcomes)
            if signature in unique_behaviors:
                continue
            structure = structural_fingerprint(source, alphabet)
            if structure in unique_structures:
                continue
            unique_behaviors.add(signature)
            unique_structures.add(structure)
            properties = behavior_properties(source, alphabet, probes, outcomes)
            description = describe_mined_program(source, alphabet, 3)
            if description is None and not allow_io_only:
                continue
            cluster = tuple(name for name, enabled in properties.items() if enabled)
            concepts = ("program_mining", "bounded_execution") + cluster
            domain = (
                "encoding_decoding"
                if properties["possible_encoder"]
                else "string_normalization"
                if properties["possible_normalizer"]
                else "rewrite_systems"
            )
            clusters[cluster].append(
                GeneratedProgram(
                    program=source,
                    template_family="mined_short_program",
                    template_version="1.0.0",
                    generator_name="bounded_program_miner",
                    generator_version="1.0.0",
                    difficulty=min(5, 2 + len(source.splitlines())),
                    allowed_features=tuple(
                        feature
                        for feature in ("start", "end", "once", "return")
                        if "(%s)" % feature in source
                    )
                    or ("plain_rewrite",),
                    parameters={
                        "input_alphabet": list(alphabet),
                        "min_input_length": 0,
                        "max_input_length": 3,
                        "behavior_properties": properties,
                        "operation_sequence": ["mined_rule"] * len(source.splitlines()),
                        "marker_allocation": [],
                    },
                    description=(
                        description
                        or "仅用于本地执行、轨迹和有限域等价性辅助任务。"
                    ),
                    tags=(
                        ("diversity", "mined", "described")
                        if description is not None
                        else ("diversity", "mined", "io_only")
                    ),
                    limits={
                        "max_program_lines": config.max_program_lines,
                        "max_program_characters": config.max_program_characters,
                        "max_string_length": config.max_string_length,
                    },
                    concepts=tuple(dict.fromkeys(concepts)),
                    task_domain=domain,
                    algorithm_family="bounded_short_rewrite",
                    composition_depth=1,
                    required_features=tuple(
                        feature
                        for feature in ("start", "end", "once", "return", "plain_rewrite")
                        if feature == "plain_rewrite" or "(%s)" % feature in source
                    ),
                    description_style=("rules" if description is not None else "io_only"),
                    source_type="random_mined",
                )
            )

    selected = []
    ordered_clusters = sorted(clusters, key=lambda key: (len(clusters[key]), key))
    while len(selected) < limit and ordered_clusters:
        next_clusters = []
        for cluster in ordered_clusters:
            if clusters[cluster] and len(selected) < limit:
                selected.append(clusters[cluster].popleft())
            if clusters[cluster]:
                next_clusters.append(cluster)
        ordered_clusters = next_clusters
    return tuple(selected)
