import unittest

from training.diversity import DiversityConfig, generate_diversity_smoke
from training.diversity_splitting import audit_diversity_splits, split_diversity_problems


class DiversitySplittingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = generate_diversity_smoke(
            DiversityConfig(count=200, seed=181, max_attempts_per_problem=40)
        )

    def test_all_generalization_splits_exist_and_pass_constraints(self):
        splits = split_diversity_problems(self.dataset.problems, seed=181)
        audit = audit_diversity_splits(splits)
        self.assertTrue(audit["passed"], audit)
        self.assertEqual(200, sum(audit["split_sizes"].values()))
        self.assertTrue(all(value > 0 for value in audit["split_sizes"].values()))

    def test_split_is_reproducible(self):
        first = split_diversity_problems(self.dataset.problems, seed=181)
        second = split_diversity_problems(self.dataset.problems, seed=181)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
