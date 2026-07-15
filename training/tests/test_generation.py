import inspect
import random
import unittest

from A2B import execute, parse
from training import (
    FailureReason,
    GeneratedProgram,
    GenerationConfig,
    GenerationExhausted,
    GenerationRejected,
    ProblemGenerator,
    TemplateCatalog,
    default_template_catalog,
)
from training.templates import BUILTIN_TEMPLATES


class TemplateContractTests(unittest.TestCase):
    def test_every_builtin_has_stable_metadata_and_valid_output(self):
        config = GenerationConfig(
            max_program_lines=40,
            max_program_characters=256,
            max_string_length=37,
        )
        for template_type in BUILTIN_TEMPLATES:
            template = template_type()
            generated = template.generate_program(random.Random(123), config)
            self.assertTrue(template.name)
            self.assertRegex(template.version, r"^\d+\.\d+\.\d+$")
            self.assertIsInstance(generated, GeneratedProgram)
            self.assertEqual(template.name, generated.template_family)
            self.assertEqual(template.version, generated.template_version)
            self.assertTrue(generated.description)
            self.assertIn("level_%d" % generated.difficulty, generated.tags)
            self.assertTrue(generated.allowed_features)
            self.assertIsInstance(generated.parameters, dict)
            self.assertEqual(37, generated.limits["max_string_length"])
            self.assertEqual(256, generated.limits["max_program_characters"])
            self.assertLessEqual(len(generated.program.splitlines()), 40)
            self.assertLessEqual(len(generated.program), 256)
            parse(generated.program)

    def test_template_api_has_no_tests_or_hidden_tests_parameter(self):
        for template_type in BUILTIN_TEMPLATES:
            parameters = tuple(
                inspect.signature(template_type.generate_program).parameters
            )
            self.assertEqual(("self", "rng", "config"), parameters)

    def test_templates_use_injected_rng_deterministically(self):
        config = GenerationConfig()
        for template_type in BUILTIN_TEMPLATES:
            first = template_type().generate_program(random.Random(99), config)
            second = template_type().generate_program(random.Random(99), config)
            self.assertEqual(first, second)


class CatalogTests(unittest.TestCase):
    def test_each_template_can_be_enabled_individually(self):
        catalog = default_template_catalog()
        for name in catalog.names:
            config = GenerationConfig(enabled_templates={name})
            generated = catalog.generate_one(random.Random(1), config)
            self.assertEqual(name, generated.template_family)

    def test_disable_and_zero_weight_remove_templates(self):
        catalog = default_template_catalog()
        config = GenerationConfig(
            enabled_templates={
                "plain_substitution",
                "anchored_trim",
                "contains_character",
            },
            disabled_templates={"plain_substitution"},
            template_weights={"anchored_trim": 5.0, "contains_character": 0.0},
        )
        batch = catalog.generate_many(random.Random(3), config, 10)
        self.assertEqual(
            {"anchored_trim"},
            {program.template_family for program in batch.programs},
        )
        self.assertEqual(10, batch.stats.successes)
        self.assertEqual(10, batch.stats.attempts)

    def test_all_disabled_is_an_immediate_configuration_error(self):
        catalog = default_template_catalog()
        config = GenerationConfig(disabled_templates=set(catalog.names))
        with self.assertRaisesRegex(ValueError, "no enabled template"):
            catalog.generate_one(random.Random(1), config)

    def test_program_and_string_limits_are_propagated(self):
        catalog = default_template_catalog()
        config = GenerationConfig(
            max_program_lines=1,
            max_program_characters=64,
            max_string_length=8,
            enabled_templates={"once_delete"},
        )
        generated = catalog.generate_one(random.Random(7), config)
        self.assertEqual(1, len(generated.program.splitlines()))
        self.assertEqual(64, generated.limits["max_program_characters"])
        self.assertEqual(8, generated.limits["max_string_length"])

    def test_weighted_selection_is_reproducible(self):
        catalog = default_template_catalog()
        config = GenerationConfig(max_attempts=3)
        first = catalog.generate_many(random.Random(1234), config, 30)
        second = catalog.generate_many(random.Random(1234), config, 30)
        self.assertEqual(first.programs, second.programs)
        self.assertEqual(first.stats.selected_templates, second.stats.selected_templates)


class FailureAccountingTests(unittest.TestCase):
    def test_rejections_stop_at_max_attempts_and_are_counted(self):
        class AlwaysReject(ProblemGenerator):
            name = "always_reject"
            version = "1.0.0"

            def generate_program(self, rng, config):
                raise GenerationRejected(FailureReason.TRIVIAL_BEHAVIOR)

        catalog = TemplateCatalog([AlwaysReject()])
        config = GenerationConfig(max_attempts=4)
        with self.assertRaises(GenerationExhausted) as raised:
            catalog.generate_one(random.Random(1), config)
        stats = raised.exception.stats
        self.assertEqual(4, stats.attempts)
        self.assertEqual(0, stats.successes)
        self.assertEqual(4, stats.failures["trivial_behavior"])

    def test_syntax_failures_are_counted(self):
        class InvalidSyntax(ProblemGenerator):
            name = "invalid_syntax"
            version = "1.0.0"

            def generate_program(self, rng, config):
                return GeneratedProgram(
                    program="not-a-rule",
                    template_family=self.name,
                    template_version=self.version,
                    generator_name=self.name,
                    generator_version=self.version,
                    difficulty=1,
                    allowed_features=("plain_rewrite",),
                    parameters={},
                    description="invalid on purpose",
                    limits={
                        "max_program_lines": config.max_program_lines,
                        "max_program_characters": config.max_program_characters,
                        "max_string_length": config.max_string_length,
                    },
                    concepts=("invalid_syntax",),
                    task_domain="rewrite_systems",
                    algorithm_family="invalid_syntax",
                    required_features=("plain_rewrite",),
                )

        catalog = TemplateCatalog([InvalidSyntax()])
        with self.assertRaises(GenerationExhausted) as raised:
            catalog.generate_one(
                random.Random(1), GenerationConfig(max_attempts=2)
            )
        self.assertEqual(2, raised.exception.stats.failures["syntax_error"])


class RepresentativeBehaviorTests(unittest.TestCase):
    def test_generated_templates_have_expected_behavior(self):
        catalog = default_template_catalog()

        increment = catalog.generate_one(
            random.Random(2),
            GenerationConfig(enabled_templates={"binary_increment"}),
        )
        program = parse(increment.program)
        self.assertEqual("10", execute(program, "1"))
        self.assertEqual("1000", execute(program, "111"))

        trim = catalog.generate_one(
            random.Random(2),
            GenerationConfig(enabled_templates={"anchored_trim"}),
        )
        char = trim.parameters["trim_character"]
        other = next(value for value in "abc" if value != char)
        self.assertEqual(other, execute(parse(trim.program), char + other + char))

    def test_program_driven_rewrites_are_acyclic_and_match_description_parameters(self):
        generated = default_template_catalog().generate_one(
            random.Random(22),
            GenerationConfig(enabled_templates={"safe_random_rewrite"}),
        )
        program = parse(generated.program)
        for source, target in generated.parameters["final_mapping"].items():
            self.assertEqual(target, execute(program, source))
        self.assertIn("program_driven", generated.tags)


if __name__ == "__main__":
    unittest.main()
