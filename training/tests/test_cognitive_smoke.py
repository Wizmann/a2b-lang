import tempfile
import unittest
from collections import Counter
from pathlib import Path

from training.schema import validate_cognitive_task
from training.cognitive_smoke import (
    MAX_PROGRAM_CHARACTERS,
    MAX_PROGRAM_LINES,
    audit_cognitive_smoke,
    generate_cognitive_smoke,
    split_cognitive,
    write_cognitive_smoke,
)


ROOT = Path(__file__).resolve().parents[2]


class CognitiveSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.problems = generate_cognitive_smoke(ROOT, seed=20260715)

    def test_catalog_has_twenty_balanced_families_and_unique_archetypes(self):
        self.assertEqual(len(self.problems), 60)
        families = Counter(
            problem.hardening["cognitive_family"] for problem in self.problems
        )
        self.assertEqual(len(families), 20)
        self.assertEqual(set(families.values()), {3})
        self.assertEqual(
            len(
                {
                    problem.hardening["semantic_archetype"]
                    for problem in self.problems
                }
            ),
            60,
        )

    def test_every_problem_is_cognitive_schema_valid_and_bounded(self):
        for problem in self.problems:
            validate_cognitive_task(problem.to_task_record())
            source = problem.generated_program.program
            self.assertLessEqual(len(source.splitlines()), MAX_PROGRAM_LINES)
            self.assertLessEqual(len(source), MAX_PROGRAM_CHARACTERS)
            self.assertEqual(
                problem.hardening["audit_reference_verification"]["fraction"],
                1.0,
            )

    def test_no_behavior_or_alpha_equivalent_duplicates(self):
        self.assertEqual(
            len({problem.behavior_signature for problem in self.problems}), 60
        )
        self.assertEqual(
            len(
                {
                    problem.hardening["alpha_equivalence_class"]
                    for problem in self.problems
                }
            ),
            60,
        )

    def test_same_seed_reproduces_all_synthesis_records(self):
        repeated = generate_cognitive_smoke(ROOT, seed=20260715)
        self.assertEqual(
            [problem.to_task_record() for problem in self.problems],
            [problem.to_task_record() for problem in repeated],
        )

    def test_all_declared_compositions_pass_component_ablation(self):
        compositions = [
            problem
            for problem in self.problems
            if problem.generated_program.composition_depth > 1
        ]
        self.assertEqual(len(compositions), 10)
        self.assertTrue(
            all(
                problem.hardening["composition_component_probe"][
                    "all_components_effective"
                ]
                for problem in compositions
            )
        )

    def test_split_is_forty_ten_ten(self):
        splits = split_cognitive(self.problems, seed=20260715)
        self.assertEqual(
            {name: len(values) for name, values in splits.items()},
            {"train": 40, "validation": 10, "test": 10},
        )

    def test_artifact_round_trip_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "dataset_smoke"
            result = write_cognitive_smoke(ROOT, directory, seed=20260715)
            self.assertTrue(result["checks"]["passed"])
            self.assertTrue(result["audit"]["passed"])
            self.assertTrue(audit_cognitive_smoke(directory)["passed"])


if __name__ == "__main__":
    unittest.main()
