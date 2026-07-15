import json
import random
import unittest

from training.diversity import DiversityConfig, generate_diversity_smoke
from training.diversity_splitting import audit_diversity_splits, split_diversity_problems
from training.diversity_statistics import diversity_exit_checks, diversity_statistics
from training.fingerprints import structural_fingerprint
from training.generation import GenerationConfig
from training.novelty import (
    build_novelty_teacher_prompt,
    novelty_inventory,
    verify_teacher_proposal,
)
from training.schema import validate_task


class DiversitySmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = generate_diversity_smoke(
            DiversityConfig(count=200, seed=515, max_attempts_per_problem=40)
        )
        cls.splits = split_diversity_problems(cls.dataset.problems, seed=515)
        cls.audit = audit_diversity_splits(cls.splits)
        cls.statistics = diversity_statistics(
            cls.dataset.problems, cls.splits, cls.audit
        )

    def test_smoke_meets_all_hard_exit_conditions(self):
        checks = diversity_exit_checks(self.statistics)
        self.assertTrue(checks["passed"], checks)
        self.assertEqual(
            len(self.dataset.problems),
            len({problem.behavior_signature for problem in self.dataset.problems}),
        )
        for problem in self.dataset.problems:
            validate_task(problem.to_task_record())
            for phrase in (
                "根据公开样例",
                "根据公开输入输出样例",
                "小型文本机器",
                "操作顺序",
                "依次删除字符集合",
                "步骤 1",
            ):
                self.assertNotIn(phrase, problem.generated_program.description)

    def test_inventory_and_teacher_prompt_request_real_novelty(self):
        inventory = novelty_inventory(self.dataset.problems)
        self.assertGreaterEqual(len(inventory["concepts"]), 20)
        prompt = build_novelty_teacher_prompt("A=B language", self.dataset.problems)
        self.assertIn("at least two computational concepts", prompt)
        self.assertIn("expected outputs", prompt)
        self.assertIn("algorithm_families", prompt)

    def test_teacher_expected_outputs_are_ignored_and_recomputed_locally(self):
        proposal = {
            "program": "a=b\nbb=b",
            "description": "先把 a 映射为 b，再规范化连续的 b。",
            "input_alphabet": ["a", "b"],
            "min_input_length": 0,
            "max_input_length": 3,
            "boundary_inputs": ["", "aaa", "bbb"],
            "concepts": ["character_mapping", "run_normalization"],
            "required_features": ["plain_rewrite"],
            "algorithm_family": "teacher_map_then_normalize",
            "task_domain": "string_normalization",
            "description_style": "direct",
            "termination_reason": "a 的数量先严格下降，随后每次压缩都会缩短字符串。",
            "nearest_difference": "组合了映射与幂等规范化。",
            "operation_sequence": ["map", "normalize_runs"],
            "expected_outputs": [{"input": "aaa", "output": "WRONG"}],
        }
        problem, score = verify_teacher_proposal(
            proposal,
            random.Random(4),
            GenerationConfig(max_program_lines=20, max_string_length=8),
            existing_problems=(),
        )
        cases = problem.public_tests + problem.hidden_tests
        self.assertIn({"input": "aaa", "output": "b"}, cases)
        self.assertGreater(score.total, 0)
        self.assertEqual("teacher", problem.generated_program.source_type)


class FingerprintTests(unittest.TestCase):
    def test_alpha_renamed_inputs_and_markers_share_structure(self):
        first = structural_fingerprint("(once)=(start)X\nXa=bX\nX=", ("a", "b"))
        second = structural_fingerprint("(once)=(start)Q\nQx=yQ\nQ=", ("x", "y"))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
