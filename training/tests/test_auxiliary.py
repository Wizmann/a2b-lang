import random
import unittest

from training.dataset import InputPoolConfig, ProblemBuildConfig, generate_dataset
from training.generation import GenerationConfig
from training.templates import default_template_catalog
from training.auxiliary import bounded_trace, generate_auxiliary_tasks


class AuxiliaryTaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.problems = generate_dataset(
            default_template_catalog(),
            seed=71,
            count=8,
            generation_config=GenerationConfig(max_attempts=30, max_string_length=8),
            build_config=ProblemBuildConfig(
                public_test_count=5,
                hidden_test_count=8,
                input_pool=InputPoolConfig(pool_size=30),
            ),
        ).problems

    def test_bounded_trace_produces_all_statuses_locally(self):
        self.assertEqual("halted", bounded_trace("a=b", "a", step_limit=5, length_limit=5)["status"])
        self.assertEqual("step_limit", bounded_trace("a=a", "a", step_limit=2, length_limit=5)["status"])
        self.assertEqual("length_limit", bounded_trace("a=aa", "a", step_limit=10, length_limit=3)["status"])

    def test_all_auxiliary_types_are_locally_labelled(self):
        tasks = generate_auxiliary_tasks(self.problems, seed=9)
        for name in (
            "execution",
            "trace",
            "repair",
            "completion",
            "ordering",
            "bounded_termination",
            "finite_domain_equivalence",
            "distinguishing_input",
        ):
            self.assertIn(name, tasks)
            self.assertTrue(tasks[name], name)
        labels = {item["label"] for item in tasks["bounded_termination"]}
        self.assertTrue({"halted", "step_limit", "length_limit"} <= labels)


if __name__ == "__main__":
    unittest.main()
