import unittest

from training import GenerationConfig, default_template_catalog
from training.baselines import run_baselines
from training.dataset import InputPoolConfig, ProblemBuildConfig, generate_dataset


class BaselineTests(unittest.TestCase):
    def test_non_neural_baseline_table_counts_public_and_hidden(self):
        dataset = generate_dataset(
            default_template_catalog(),
            seed=901,
            count=8,
            generation_config=GenerationConfig(
                max_attempts=30, max_string_length=5
            ),
            build_config=ProblemBuildConfig(
                public_test_count=4,
                hidden_test_count=8,
                input_pool=InputPoolConfig(pool_size=30),
            ),
        )
        results = run_baselines(dataset.problems)
        self.assertEqual(
            {"identity", "constant", "single_rule_search", "template_search"},
            {result.baseline for result in results},
        )
        for result in results:
            self.assertEqual(len(dataset.problems), result.attempted)
            self.assertLessEqual(result.hidden_solved, result.public_solved)
            self.assertEqual(
                result.public_solved,
                result.hidden_solved + result.public_only_overfit,
            )


if __name__ == "__main__":
    unittest.main()
