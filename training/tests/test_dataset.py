import random
import unittest

from training import GenerationConfig, default_template_catalog
from training.dataset import (
    InputPoolConfig,
    ProblemBuildConfig,
    behavior_signature,
    build_input_pool,
    build_problem,
    evaluate_inputs,
    generate_dataset,
)
from training.schema import validate_task


class InputAndProblemTests(unittest.TestCase):
    def setUp(self):
        self.catalog = default_template_catalog()

    def generated(self, name, seed=1, max_string_length=6):
        return self.catalog.generate_one(
            random.Random(seed),
            GenerationConfig(
                enabled_templates={name},
                max_string_length=max_string_length,
            ),
        )

    def test_pool_includes_empty_and_boundary_inputs(self):
        generated = self.generated("plain_substitution", max_string_length=4)
        pool = build_input_pool(
            random.Random(1),
            generated,
            InputPoolConfig(pool_size=30, exhaustive_max_length=2),
        )
        self.assertIn("", pool)
        self.assertTrue(any(len(value) == 4 for value in pool))
        self.assertEqual(len(pool), len(set(pool)))

    def test_binary_pool_has_no_multidigit_leading_zero(self):
        generated = self.generated("binary_increment", max_string_length=5)
        pool = build_input_pool(
            random.Random(2),
            generated,
            InputPoolConfig(pool_size=20, exhaustive_max_length=3),
        )
        self.assertTrue(pool)
        self.assertTrue(all(not (len(value) > 1 and value[0] == "0") for value in pool))
        self.assertLessEqual(max(map(len, pool)), 4)

    def test_problem_has_disjoint_tests_signature_and_valid_schema(self):
        generated = self.generated("anchored_trim")
        problem = build_problem(
            random.Random(3),
            generated,
            ProblemBuildConfig(
                public_test_count=4,
                hidden_test_count=12,
                input_pool=InputPoolConfig(pool_size=40),
            ),
        )
        public_inputs = {case["input"] for case in problem.public_tests}
        hidden_inputs = {case["input"] for case in problem.hidden_tests}
        self.assertFalse(public_inputs & hidden_inputs)
        self.assertEqual(64, len(problem.behavior_signature))
        self.assertEqual(1.0, problem.quality.terminating_fraction)
        self.assertTrue(
            any(case["input"] != case["output"] for case in problem.public_tests)
        )
        validate_task(problem.to_task_record())

    def test_signature_is_stable_for_same_probe_behavior(self):
        generated = self.generated("once_delete", seed=8)
        config = ProblemBuildConfig(input_pool=InputPoolConfig(pool_size=35))
        inputs = build_input_pool(random.Random(9), generated, config.input_pool)
        first = evaluate_inputs(generated, inputs, config)
        second = evaluate_inputs(generated, inputs, config)
        self.assertEqual(behavior_signature(first), behavior_signature(second))


class DatasetGenerationTests(unittest.TestCase):
    def test_seeded_dataset_is_reproducible_and_deduplicated(self):
        kwargs = {
            "seed": 123,
            "count": 8,
            "generation_config": GenerationConfig(
                max_attempts=20,
                max_string_length=6,
            ),
            "build_config": ProblemBuildConfig(
                public_test_count=4,
                hidden_test_count=10,
                input_pool=InputPoolConfig(pool_size=35),
            ),
        }
        first = generate_dataset(default_template_catalog(), **kwargs)
        second = generate_dataset(default_template_catalog(), **kwargs)
        self.assertEqual(first.problems, second.problems)
        self.assertEqual(8, len(first.problems))
        self.assertTrue(
            all(problem.quality.terminating_fraction == 1.0 for problem in first.problems)
        )
        signatures = {problem.behavior_signature for problem in first.problems}
        self.assertEqual(8, len(signatures))
        self.assertGreaterEqual(first.stats.failures["duplicate_behavior"], 1)

    def test_total_attempts_are_bounded(self):
        result = generate_dataset(
            default_template_catalog(),
            seed=2,
            count=20,
            generation_config=GenerationConfig(
                max_attempts=2,
                max_string_length=2,
                enabled_templates={"plain_substitution"},
            ),
            build_config=ProblemBuildConfig(
                public_test_count=2,
                hidden_test_count=2,
                input_pool=InputPoolConfig(pool_size=8),
            ),
        )
        self.assertLessEqual(result.stats.attempts, 40)
        self.assertLess(len(result.problems), result.requested)


if __name__ == "__main__":
    unittest.main()
