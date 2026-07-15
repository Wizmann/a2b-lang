"""统一且有界的程序生成器接口。"""

import math
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from A2B import A2BParseException, parse


class FailureReason(str, Enum):
    SYNTAX_ERROR = "syntax_error"
    NO_TERMINATING_INPUTS = "no_terminating_inputs"
    TRIVIAL_BEHAVIOR = "trivial_behavior"
    INSUFFICIENT_PUBLIC_TESTS = "insufficient_public_tests"
    INSUFFICIENT_HIDDEN_TESTS = "insufficient_hidden_tests"
    DUPLICATE_BEHAVIOR = "duplicate_behavior"
    DUPLICATE_STRUCTURE = "duplicate_structure"
    AMBIGUOUS_DESCRIPTION = "ambiguous_description"
    VERIFIER_FAILURE = "verifier_failure"
    RESOURCE_LIMIT = "resource_limit"


class GenerationRejected(Exception):
    """A normal, countable rejection of one generation attempt."""

    def __init__(self, reason, detail=""):
        if not isinstance(reason, FailureReason):
            reason = FailureReason(reason)
        self.reason = reason
        self.detail = detail
        super().__init__("%s%s" % (reason.value, ": " + detail if detail else ""))


class GenerationExhausted(RuntimeError):
    """Raised after exactly ``max_attempts`` unsuccessful attempts."""

    def __init__(self, max_attempts, stats):
        self.max_attempts = max_attempts
        self.stats = stats
        super().__init__("generation failed after %d attempts" % max_attempts)


def _positive_integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("%s must be a positive integer" % name)


@dataclass(frozen=True)
class GenerationConfig:
    """Controls selection, retries, and resource limits for one run."""

    max_attempts: int = 20
    max_program_lines: int = 40
    max_program_characters: int = 512
    max_string_length: int = 1000
    enabled_templates: frozenset = None
    disabled_templates: frozenset = field(default_factory=frozenset)
    template_weights: dict = field(default_factory=dict)

    def __post_init__(self):
        _positive_integer(self.max_attempts, "max_attempts")
        _positive_integer(self.max_program_lines, "max_program_lines")
        _positive_integer(self.max_program_characters, "max_program_characters")
        _positive_integer(self.max_string_length, "max_string_length")

        enabled = self.enabled_templates
        if enabled is not None:
            enabled = frozenset(enabled)
            if not all(isinstance(name, str) and name for name in enabled):
                raise ValueError("enabled_templates must contain non-empty names")
            object.__setattr__(self, "enabled_templates", enabled)

        disabled = frozenset(self.disabled_templates)
        if not all(isinstance(name, str) and name for name in disabled):
            raise ValueError("disabled_templates must contain non-empty names")
        object.__setattr__(self, "disabled_templates", disabled)

        weights = dict(self.template_weights)
        for name, weight in weights.items():
            if not isinstance(name, str) or not name:
                raise ValueError("template weight names must be non-empty strings")
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise ValueError("template weights must be numbers")
            if not math.isfinite(weight) or weight < 0:
                raise ValueError("template weights must be finite and non-negative")
        object.__setattr__(self, "template_weights", MappingProxyType(weights))

    def enables(self, template_name):
        if template_name in self.disabled_templates:
            return False
        return self.enabled_templates is None or template_name in self.enabled_templates

    def weight_for(self, template_name, default_weight):
        return self.template_weights.get(template_name, default_weight)


@dataclass(frozen=True)
class GeneratedProgram:
    """Source plus complete provenance for one generated A=B program."""

    program: str
    template_family: str
    template_version: str
    generator_name: str
    generator_version: str
    difficulty: int
    allowed_features: tuple
    parameters: dict
    description: str = None
    tags: tuple = ()
    limits: dict = field(default_factory=dict)
    concepts: tuple = ()
    task_domain: str = "string_normalization"
    algorithm_family: str = "unspecified"
    composition_depth: int = 1
    required_features: tuple = ()
    description_style: str = "direct"
    source_type: str = "template"

    def __post_init__(self):
        for name in (
            "program",
            "template_family",
            "template_version",
            "generator_name",
            "generator_version",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError("%s must be a non-empty string" % name)
        if isinstance(self.difficulty, bool) or not isinstance(self.difficulty, int):
            raise ValueError("difficulty must be an integer")
        if not 1 <= self.difficulty <= 5:
            raise ValueError("difficulty must be between 1 and 5")
        if not isinstance(self.allowed_features, tuple) or not all(
            isinstance(feature, str) and feature for feature in self.allowed_features
        ):
            raise ValueError("allowed_features must be a tuple of names")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be an object")
        if self.description is not None and not isinstance(self.description, str):
            raise ValueError("description must be a string or None")
        if not isinstance(self.tags, tuple) or not all(
            isinstance(tag, str) and tag for tag in self.tags
        ):
            raise ValueError("tags must be a tuple of names")
        if not isinstance(self.limits, dict):
            raise ValueError("limits must be an object")
        if not self.concepts or not all(
            isinstance(concept, str) and concept for concept in self.concepts
        ):
            raise ValueError("concepts must contain at least one name")
        for name in ("task_domain", "algorithm_family", "description_style"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError("%s must be a non-empty string" % name)
        if (
            isinstance(self.composition_depth, bool)
            or not isinstance(self.composition_depth, int)
            or not 1 <= self.composition_depth <= 3
        ):
            raise ValueError("composition_depth must be between 1 and 3")
        if not isinstance(self.required_features, tuple) or not all(
            isinstance(feature, str) and feature for feature in self.required_features
        ):
            raise ValueError("required_features must be a tuple of names")
        if self.source_type not in {
            "template",
            "composed",
            "enumerated",
            "random_mined",
            "teacher",
            "handwritten",
        }:
            raise ValueError("invalid source_type: %s" % self.source_type)


@dataclass
class GenerationStats:
    attempts: int = 0
    successes: int = 0
    failures: Counter = field(default_factory=Counter)
    selected_templates: Counter = field(default_factory=Counter)

    def reject(self, reason):
        self.failures[reason.value] += 1


@dataclass(frozen=True)
class BatchGenerationResult:
    programs: tuple
    stats: GenerationStats


class ProblemGenerator(ABC):
    """A named and versioned program generator or template family."""

    name = None
    version = None
    default_weight = 1.0

    @abstractmethod
    def generate_program(self, rng, config):
        """Return a ``GeneratedProgram`` using only the injected RNG."""


class TemplateCatalog:
    """Registry, weighted selector, and bounded retry driver."""

    def __init__(self, templates=()):
        self._templates = {}
        for template in templates:
            self.register(template)

    @property
    def names(self):
        return tuple(sorted(self._templates))

    def register(self, template):
        if not isinstance(template, ProblemGenerator):
            raise TypeError("template must implement ProblemGenerator")
        if not isinstance(template.name, str) or not template.name:
            raise ValueError("template must have a stable non-empty name")
        if not isinstance(template.version, str) or not template.version:
            raise ValueError("template must have a non-empty version")
        if template.name in self._templates:
            raise ValueError("duplicate template name: %s" % template.name)
        if template.default_weight < 0 or not math.isfinite(template.default_weight):
            raise ValueError("template default_weight must be finite and non-negative")
        self._templates[template.name] = template

    def get(self, name):
        return self._templates[name]

    def _candidates(self, config):
        candidates = []
        for name in sorted(self._templates):
            template = self._templates[name]
            weight = config.weight_for(name, template.default_weight)
            if config.enables(name) and weight > 0:
                candidates.append((template, weight))
        if not candidates:
            raise ValueError("no enabled template has a positive sampling weight")
        return candidates

    @staticmethod
    def _choose(rng, candidates):
        total = sum(weight for _, weight in candidates)
        point = rng.random() * total
        running = 0.0
        for template, weight in candidates:
            running += weight
            if point < running:
                return template
        return candidates[-1][0]

    @staticmethod
    def _validate_generated(generated, template, config):
        if not isinstance(generated, GeneratedProgram):
            raise GenerationRejected(
                FailureReason.VERIFIER_FAILURE,
                "generator did not return GeneratedProgram",
            )
        if (
            generated.template_family != template.name
            or generated.template_version != template.version
            or generated.generator_name != template.name
            or generated.generator_version != template.version
        ):
            raise GenerationRejected(
                FailureReason.VERIFIER_FAILURE,
                "generated provenance does not match selected template",
            )
        if not generated.description or not generated.description.strip():
            raise GenerationRejected(
                FailureReason.AMBIGUOUS_DESCRIPTION,
                "template did not provide a description",
            )

        lines = generated.program.splitlines()
        if len(lines) > config.max_program_lines:
            raise GenerationRejected(
                FailureReason.RESOURCE_LIMIT,
                "program has %d lines; limit is %d"
                % (len(lines), config.max_program_lines),
            )
        if len(generated.program) > config.max_program_characters:
            raise GenerationRejected(
                FailureReason.RESOURCE_LIMIT,
                "program has %d characters; limit is %d"
                % (len(generated.program), config.max_program_characters),
            )
        if generated.limits.get("max_program_lines") != config.max_program_lines:
            raise GenerationRejected(
                FailureReason.VERIFIER_FAILURE,
                "template did not preserve max_program_lines",
            )
        if (
            generated.limits.get("max_program_characters")
            != config.max_program_characters
        ):
            raise GenerationRejected(
                FailureReason.VERIFIER_FAILURE,
                "template did not preserve max_program_characters",
            )
        if generated.limits.get("max_string_length") != config.max_string_length:
            raise GenerationRejected(
                FailureReason.VERIFIER_FAILURE,
                "template did not preserve max_string_length",
            )
        try:
            parse(generated.program)
        except A2BParseException as error:
            raise GenerationRejected(FailureReason.SYNTAX_ERROR, str(error)) from error
        return generated

    def generate_one(self, rng, config, stats=None):
        if not isinstance(config, GenerationConfig):
            raise TypeError("config must be GenerationConfig")
        stats = stats if stats is not None else GenerationStats()
        for _ in range(config.max_attempts):
            try:
                return self.generate_attempt(rng, config, stats=stats)
            except GenerationRejected:
                continue
        raise GenerationExhausted(config.max_attempts, stats)

    def generate_attempt(self, rng, config, stats=None):
        """Perform exactly one selectable and countable generation attempt."""
        if not isinstance(config, GenerationConfig):
            raise TypeError("config must be GenerationConfig")
        stats = stats if stats is not None else GenerationStats()
        template = self._choose(rng, self._candidates(config))
        stats.attempts += 1
        stats.selected_templates[template.name] += 1
        try:
            generated = template.generate_program(rng, config)
            generated = self._validate_generated(generated, template, config)
        except GenerationRejected as rejection:
            stats.reject(rejection.reason)
            raise
        stats.successes += 1
        return generated

    def generate_many(self, rng, config, count):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("count must be a non-negative integer")
        stats = GenerationStats()
        programs = tuple(
            self.generate_one(rng, config, stats=stats) for _ in range(count)
        )
        return BatchGenerationResult(programs=programs, stats=stats)
