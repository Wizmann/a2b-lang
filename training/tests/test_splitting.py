import unittest

from training import GenerationConfig, default_template_catalog
from training.dataset import InputPoolConfig, ProblemBuildConfig, generate_dataset
from training.splitting import SplitConfig, audit_leakage, split_problems
from training.statistics import quality_statistics


class SplitAndAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = generate_dataset(
            default_template_catalog(),
            seed=88,
            count=12,
            generation_config=GenerationConfig(
                max_attempts=30, max_string_length=6
            ),
            build_config=ProblemBuildConfig(
                public_test_count=4,
                hidden_test_count=8,
                input_pool=InputPoolConfig(pool_size=30),
            ),
        )

    def test_family_split_is_reproducible_and_has_no_leakage(self):
        first = split_problems(self.dataset.problems, seed=91)
        second = split_problems(self.dataset.problems, seed=91)
        self.assertEqual(first, second)
        self.assertEqual(len(self.dataset.problems), sum(map(len, first.as_dict().values())))
        audit = audit_leakage(first)
        self.assertTrue(audit.passed)

    def test_statistics_include_required_quality_fields(self):
        splits = split_problems(self.dataset.problems, seed=92)
        stats = quality_statistics(self.dataset.problems, splits)
        for field in (
            "identity_fraction",
            "constant_fraction",
            "terminating_fraction",
            "program_line_distribution",
            "execution_step_distribution",
            "public_hidden_overlap",
            "behavior_duplicates",
            "leakage_audit",
            "split_sizes",
        ):
            self.assertIn(field, stats)
        self.assertTrue(stats["leakage_audit"]["passed"])

    def test_signature_grouping_can_be_selected(self):
        splits = split_problems(
            self.dataset.problems,
            seed=93,
            config=SplitConfig(group_by_template_family=False),
        )
        self.assertEqual(0, audit_leakage(splits).signature_cross_split)


if __name__ == "__main__":
    unittest.main()
