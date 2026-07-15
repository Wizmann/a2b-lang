import tempfile
import unittest
from pathlib import Path

from training import GenerationConfig, default_template_catalog
from training.dataset import InputPoolConfig, ProblemBuildConfig, build_problem
from training.teacher import (
    MockTeacherProvider,
    TeacherCache,
    TeacherPipeline,
    TeacherRoles,
    extract_candidate,
    verify_candidate,
)

import random


LANGUAGE = "每行使用 左侧=右侧；允许 (start)、(end)、(once)、(return)。"
OUTPUT = "只输出 <program> 标签中的 A=B 程序。"


def plain_problem():
    catalog = default_template_catalog()
    generated = catalog.generate_one(
        random.Random(4),
        GenerationConfig(
            enabled_templates={"plain_substitution"}, max_string_length=5
        ),
    )
    return build_problem(
        random.Random(5),
        generated,
        ProblemBuildConfig(
            public_test_count=4,
            hidden_test_count=8,
            input_pool=InputPoolConfig(pool_size=30),
        ),
    )


class TeacherTests(unittest.TestCase):
    def test_candidate_extraction_supports_tags_and_fences(self):
        self.assertEqual(("a=b", True), extract_candidate("<program>\na=b\n</program>"))
        self.assertEqual(("a=b", True), extract_candidate("```a2b\na=b\n```"))

    def test_single_line_lookup_program_is_bounded_by_character_limit(self):
        problem = plain_problem()
        limit = problem.generated_program.limits["max_program_characters"]
        oversized = ("a" * limit) + "=b"
        verification = verify_candidate(oversized, problem)
        self.assertFalse(verification.verified)
        self.assertEqual("character_limit", verification.failure_stage)

    def test_mock_pipeline_verifies_solution_without_hidden_prompt_leak(self):
        problem = plain_problem()
        provider = MockTeacherProvider(
            ["<program>\n%s\n</program>" % problem.generated_program.program]
        )
        pipeline = TeacherPipeline(provider)
        result = pipeline.solve(problem, LANGUAGE, OUTPUT, max_repairs=0)
        self.assertTrue(result.solved)
        prompt = provider.calls[0]["messages"][1]["content"]
        for case in problem.hidden_tests:
            # Check serialized pairs, avoiding false positives for shared substrings.
            import json
            self.assertNotIn(
                json.dumps(case, ensure_ascii=False, separators=(",", ":")),
                prompt,
            )
        self.assertNotIn(problem.generated_program.program, prompt)
        self.assertNotIn(problem.behavior_signature, prompt)

    def test_repair_uses_public_counterexample(self):
        problem = plain_problem()
        provider = MockTeacherProvider(
            [
                "<program>\n\n</program>",
                "<program>\n%s\n</program>" % problem.generated_program.program,
            ]
        )
        pipeline = TeacherPipeline(
            provider,
            roles=TeacherRoles(primary="primary", repair="repair"),
        )
        result = pipeline.solve(problem, LANGUAGE, OUTPUT, max_repairs=1)
        self.assertTrue(result.solved)
        self.assertEqual(("primary", "repair"), tuple(a.model for a in result.attempts))
        self.assertIsNotNone(result.attempts[1].disclosed_counterexample)

    def test_cache_avoids_duplicate_provider_call(self):
        problem = plain_problem()
        response = "<program>\n%s\n</program>" % problem.generated_program.program
        provider = MockTeacherProvider([response])
        with tempfile.TemporaryDirectory() as directory:
            pipeline = TeacherPipeline(
                provider, cache=TeacherCache(Path(directory) / "cache")
            )
            first = pipeline.solve(problem, LANGUAGE, OUTPUT, max_repairs=0)
            second = pipeline.solve(problem, LANGUAGE, OUTPUT, max_repairs=0)
        self.assertFalse(first.attempts[0].cached)
        self.assertTrue(second.attempts[0].cached)
        self.assertEqual(1, len(provider.calls))


if __name__ == "__main__":
    unittest.main()
