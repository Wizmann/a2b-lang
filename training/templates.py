"""Built-in, hand-written template families for Levels 1 through 5."""

from .generation import (
    FailureReason,
    GeneratedProgram,
    GenerationRejected,
    ProblemGenerator,
    TemplateCatalog,
)


GENERATOR_VERSION = "1.0.0"
ALPHABET = ("a", "b", "c")


def _choice(rng, values):
    return values[rng.randrange(len(values))]


def _require_lines(config, required):
    if required > config.max_program_lines:
        raise GenerationRejected(
            FailureReason.RESOURCE_LIMIT,
            "template requires %d program lines; limit is %d"
            % (required, config.max_program_lines),
        )


def _generated(template, config, *, program, difficulty, features, parameters,
               description, tags, concepts=None, task_domain=None,
               algorithm_family=None, composition_depth=1,
               description_style="direct", source_type="template"):
    defaults = {
        "plain_substitution": (("character_mapping", "substitution"), "string_normalization"),
        "contains_character": (("pattern_recognition", "classification"), "pattern_recognition"),
        "anchored_trim": (("anchored_matching", "boundary_normalization"), "string_normalization"),
        "once_delete": (("bounded_rewrite", "deletion", "once_state"), "string_normalization"),
        "binary_increment": (("binary_arithmetic", "carry_propagation", "marker_rewrite"), "binary_operations"),
        "safe_random_rewrite": (("acyclic_rewrite", "character_mapping"), "rewrite_systems"),
    }
    default_concepts, default_domain = defaults.get(
        template.name, (("rewrite",), "rewrite_systems")
    )
    return GeneratedProgram(
        program=program,
        template_family=template.name,
        template_version=template.version,
        generator_name=template.name,
        generator_version=template.version,
        difficulty=difficulty,
        allowed_features=tuple(features),
        parameters=dict(parameters),
        description=description,
        tags=tuple(tags),
        limits={
            "max_program_lines": config.max_program_lines,
            "max_program_characters": config.max_program_characters,
            "max_string_length": config.max_string_length,
        },
        concepts=tuple(concepts or default_concepts),
        task_domain=task_domain or default_domain,
        algorithm_family=algorithm_family or template.name,
        composition_depth=composition_depth,
        required_features=tuple(features),
        description_style=description_style,
        source_type=("random_mined" if template.name == "safe_random_rewrite" else source_type),
    )


class PlainSubstitutionTemplate(ProblemGenerator):
    name = "plain_substitution"
    version = GENERATOR_VERSION
    default_weight = 3.0

    def generate_program(self, rng, config):
        _require_lines(config, 1)
        source = _choice(rng, ALPHABET)
        target = _choice(rng, tuple(char for char in ALPHABET if char != source))
        return _generated(
            self,
            config,
            program="%s=%s" % (source, target),
            difficulty=1,
            features=("plain_rewrite",),
            parameters={
                "source": source,
                "target": target,
                "input_alphabet": list(ALPHABET),
                "min_input_length": 0,
                "max_input_length": config.max_string_length,
            },
            description="将输入中的每个 %s 替换为 %s，其他字符保持不变。"
            % (source, target),
            tags=("level_1", "character_mapping"),
        )


class ContainsCharacterTemplate(ProblemGenerator):
    name = "contains_character"
    version = GENERATOR_VERSION
    default_weight = 2.0

    def generate_program(self, rng, config):
        _require_lines(config, 2)
        if config.max_string_length < len("false"):
            raise GenerationRejected(
                FailureReason.RESOURCE_LIMIT,
                "contains_character requires max_string_length >= 5",
            )
        needle = _choice(rng, ALPHABET)
        return _generated(
            self,
            config,
            program="%s=(return)true\n=(return)false" % needle,
            difficulty=2,
            features=("plain_rewrite", "return", "empty_pattern"),
            parameters={
                "needle": needle,
                "input_alphabet": list(ALPHABET),
                "min_input_length": 0,
                "max_input_length": config.max_string_length,
            },
            description="如果输入包含字符 %s，输出 true；否则输出 false。" % needle,
            tags=("level_2", "predicate"),
        )


class AnchoredTrimTemplate(ProblemGenerator):
    name = "anchored_trim"
    version = GENERATOR_VERSION
    default_weight = 2.0

    def generate_program(self, rng, config):
        _require_lines(config, 2)
        char = _choice(rng, ALPHABET)
        return _generated(
            self,
            config,
            program="(start)%s=\n(end)%s=" % (char, char),
            difficulty=3,
            features=("start", "end", "plain_rewrite"),
            parameters={
                "trim_character": char,
                "input_alphabet": list(ALPHABET),
                "min_input_length": 0,
                "max_input_length": config.max_string_length,
            },
            description="删除输入开头和结尾连续出现的字符 %s。" % char,
            tags=("level_3", "anchored_rewrite"),
        )


class OnceDeleteTemplate(ProblemGenerator):
    name = "once_delete"
    version = GENERATOR_VERSION
    default_weight = 1.5

    def generate_program(self, rng, config):
        max_deletions = min(4, config.max_program_lines)
        _require_lines(config, 1)
        char = _choice(rng, ALPHABET)
        deletions = rng.randint(1, max_deletions)
        program = "\n".join("(once)%s=" % char for _ in range(deletions))
        return _generated(
            self,
            config,
            program=program,
            difficulty=4,
            features=("once", "plain_rewrite"),
            parameters={
                "character": char,
                "deletions": deletions,
                "input_alphabet": list(ALPHABET),
                "min_input_length": 0,
                "max_input_length": config.max_string_length,
            },
            description="删除输入中最靠左的至多 %d 个字符 %s。"
            % (deletions, char),
            tags=("level_4", "bounded_rewrite"),
        )


class BinaryIncrementTemplate(ProblemGenerator):
    name = "binary_increment"
    version = GENERATOR_VERSION
    default_weight = 0.5

    def generate_program(self, rng, config):
        _require_lines(config, 4)
        if config.max_string_length < 2:
            raise GenerationRejected(
                FailureReason.RESOURCE_LIMIT,
                "binary_increment requires max_string_length >= 2",
            )
        marker = _choice(rng, ("X", "Y", "Z"))
        return _generated(
            self,
            config,
            program="\n".join(
                (
                    "(once)=(end)%s" % marker,
                    "0%s=1" % marker,
                    "1%s=%s0" % (marker, marker),
                    "%s=1" % marker,
                )
            ),
            difficulty=5,
            features=("once", "end", "empty_pattern", "marker_propagation"),
            parameters={
                "marker": marker,
                "operation": "binary_increment",
                "input_alphabet": ["0", "1"],
                "min_input_length": 1,
                # Carry can grow an all-ones input by one character.
                "max_input_length": config.max_string_length - 1,
                "forbid_leading_zero": True,
            },
            description="将输入的无前导零二进制整数加一，并输出二进制结果。",
            tags=("level_5", "binary_arithmetic", "marker_algorithm"),
        )


class SafeRandomRewriteGenerator(ProblemGenerator):
    """Program-driven generator using an acyclic character rewrite graph."""

    name = "safe_random_rewrite"
    version = GENERATOR_VERSION
    default_weight = 1.0

    def generate_program(self, rng, config):
        max_rules = min(3, config.max_program_lines, len(ALPHABET) - 1)
        _require_lines(config, 1)
        rule_count = rng.randint(1, max_rules)
        sources = list(ALPHABET[:-1])
        rng.shuffle(sources)
        sources = sorted(sources[:rule_count], key=ALPHABET.index)
        rules = []
        direct = {}
        for source in sources:
            source_index = ALPHABET.index(source)
            target = _choice(rng, ALPHABET[source_index + 1 :])
            direct[source] = target
            rules.append("%s=%s" % (source, target))

        final = {}
        for char in ALPHABET:
            value = char
            while value in direct:
                value = direct[value]
            final[char] = value
        mapping = "、".join("%s→%s" % item for item in final.items())
        return _generated(
            self,
            config,
            program="\n".join(rules),
            difficulty=2 if rule_count == 1 else 3,
            features=("plain_rewrite",),
            parameters={
                "rules": direct,
                "final_mapping": final,
                "input_alphabet": list(ALPHABET),
                "min_input_length": 0,
                "max_input_length": config.max_string_length,
            },
            description="逐字符应用映射 %s，直到字符不再变化。" % mapping,
            tags=(
                "level_%d" % (2 if rule_count == 1 else 3),
                "program_driven",
                "acyclic_rewrite",
            ),
        )


BUILTIN_TEMPLATES = (
    PlainSubstitutionTemplate,
    ContainsCharacterTemplate,
    AnchoredTrimTemplate,
    OnceDeleteTemplate,
    BinaryIncrementTemplate,
    SafeRandomRewriteGenerator,
)


def default_template_catalog():
    """Return a fresh catalog containing all built-in template families."""
    return TemplateCatalog(template_type() for template_type in BUILTIN_TEMPLATES)
