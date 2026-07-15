import unittest

from training.auxiliary import generate_auxiliary_tasks
from training.hardening import HardeningConfig, generate_hardening_smoke
from training.hardening_splitting import (
    audit_hardening_splits,
    split_hardening_problems,
)
from training.hardening_statistics import (
    hardening_exit_checks,
    hardening_statistics,
)
from training.ir import IROperation, TaskIR, ir_concepts
from training.schema import validate_hardened_task


class SemanticHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = generate_hardening_smoke(
            HardeningConfig(count=240, candidate_count=300, seed=818)
        )
        cls.splits = split_hardening_problems(cls.dataset.problems, seed=818)
        split_by_problem = {
            problem.id: split
            for split, problems in cls.splits.as_dict().items()
            for problem in problems
        }
        cls.auxiliary = generate_auxiliary_tasks(
            cls.dataset.problems,
            seed=819,
            split_by_problem=split_by_problem,
        )
        cls.audit = audit_hardening_splits(cls.splits, cls.auxiliary)
        cls.statistics = hardening_statistics(
            cls.dataset.problems, cls.splits, cls.audit
        )

    def test_hardened_schema_fingerprints_and_ontology(self):
        for problem in self.dataset.problems:
            validate_hardened_task(problem.to_task_record())
            self.assertFalse(problem.hardening["ontology_errors"])
            for name in (
                "concrete_behavior_fingerprint",
                "alpha_normalized_behavior_fingerprint",
                "semantic_ir_fingerprint",
            ):
                self.assertEqual(64, len(problem.hardening[name]))
        concepts = ir_concepts(
            TaskIR(
                (
                    IROperation(
                        "unary_operation", {"operation": "binary_increment"}
                    ),
                ),
                ("0", "1"),
            )
        )
        self.assertIn("binary_arithmetic", concepts)
        self.assertNotIn("unary_arithmetic", concepts)

    def test_all_formal_compositions_are_effective(self):
        compositions = [
            problem
            for problem in self.dataset.problems
            if problem.generated_program.composition_depth > 1
        ]
        self.assertTrue(compositions)
        self.assertTrue(
            all(
                problem.hardening["effective_composition_depth"] >= 2
                for problem in compositions
            )
        )
        self.assertTrue(
            all(
                problem.generated_program.composition_depth != 3
                or len(problem.hardening["effective_components"]) == 3
                for problem in compositions
            )
        )
        self.assertGreater(
            sum(problem.hardening["genuine_composition"] for problem in compositions),
            0,
        )

    def test_controlled_benchmarks_and_lineage_have_no_leakage(self):
        self.assertTrue(self.audit["passed"], self.audit)
        for name in (
            "lineage_cross_split",
            "mutant_family_cross_split",
            "auxiliary_reference_cross_split",
            "alpha_equivalent_program_cross_split",
            "operation_order_unproved",
        ):
            self.assertEqual(0, self.audit[name], name)
        for record in self.splits.controlled_benchmarks["test_operation_order"]:
            self.assertTrue(record["oracle_proved_different"])
            self.assertIsNotNone(record["distinguishing_input"])
        for records in self.auxiliary.values():
            for record in records:
                for field in (
                    "root_problem_id",
                    "program_lineage_id",
                    "mutant_family_id",
                    "alpha_equivalence_class",
                    "split",
                ):
                    self.assertIn(field, record)

    def test_domains_specification_and_exit_checks(self):
        self.assertIn("functional", self.statistics["specification_level_counts"])
        self.assertIn("operational", self.statistics["specification_level_counts"])
        for category, result in self.statistics["length_audit"].items():
            self.assertTrue(result["problem_count"], category)
            self.assertTrue(result["all_verified"], category)
            self.assertTrue(result["has_longer_than_construction"], category)
        checks = hardening_exit_checks(self.statistics)
        self.assertTrue(checks["passed"], checks)
        for result in self.statistics["confounding_report"].values():
            self.assertIn("confounding_detected", result)
            self.assertEqual("paired_or_matched_benchmark", result["primary_control"])


if __name__ == "__main__":
    unittest.main()
