import io
import json
import random
import tempfile
import unittest
from pathlib import Path

from training import (
    JsonlError,
    ReproducibilityError,
    SchemaValidationError,
    build_prompt,
    check_reproducible,
    read_jsonl,
    read_tasks,
    validate_task,
    write_jsonl,
    write_tasks,
)


def valid_task():
    return {
        "id": "unicode-empty",
        "description": "把输入原样输出：中文说明",
        "public_tests": [{"input": "", "output": ""}],
        "hidden_tests": [{"input": "hidden-input", "output": "hidden-output"}],
        "reference_programs": ["secret-reference-program"],
        "metadata": {"source": "secret-metadata"},
        "limits": {"steps": 100, "note": "secret-limit"},
        "generator": {"name": "secret-generator"},
        "template_family": "secret-template-family",
        "standard_answer": "secret-standard-answer",
        "behavior_signature": ["secret-signature"],
        "concepts": ["identity", "unicode"],
        "task_domain": "string_normalization",
        "algorithm_family": "identity",
        "composition_depth": 1,
        "required_features": [],
        "description_style": "direct",
        "source_type": "handwritten",
        "semantic_fingerprint": "a" * 64,
        "structural_fingerprint": "b" * 64,
    }


class SchemaTests(unittest.TestCase):
    def test_valid_record_supports_empty_io_and_unicode(self):
        task = valid_task()
        self.assertIs(task, validate_task(task))

    def test_missing_reference_programs_is_rejected(self):
        task = valid_task()
        del task["reference_programs"]
        with self.assertRaisesRegex(SchemaValidationError, "reference_programs"):
            validate_task(task)

    def test_unknown_fields_and_invalid_test_shapes_are_rejected(self):
        task = valid_task()
        task["accidental_private_field"] = "secret"
        with self.assertRaisesRegex(SchemaValidationError, "unknown fields"):
            validate_task(task)

        task = valid_task()
        task["public_tests"][0]["note"] = "not part of the test schema"
        with self.assertRaisesRegex(SchemaValidationError, "exactly the fields"):
            validate_task(task)


class JsonlTests(unittest.TestCase):
    def test_task_round_trip_preserves_unicode_and_empty_strings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.jsonl"
            write_tasks(path, [valid_task()])
            raw = path.read_text(encoding="utf-8")
            self.assertIn("中文说明", raw)
            self.assertNotIn("\\u4e2d", raw)
            self.assertEqual([valid_task()], list(read_tasks(path)))

    def test_generic_line_reader_and_writer(self):
        output = io.StringIO()
        records = [{"input": "", "output": "雪"}, ""]
        write_jsonl(output, records)
        self.assertEqual(records, list(read_jsonl(io.StringIO(output.getvalue()))))
        self.assertEqual(2, len(output.getvalue().splitlines()))

    def test_blank_line_and_schema_failure_report_line_number(self):
        with self.assertRaisesRegex(JsonlError, r":2: blank lines"):
            list(read_jsonl(io.StringIO('{}\n\n')))

        malformed = json.dumps({"description": "missing fields"}) + "\n"
        with self.assertRaisesRegex(JsonlError, r":1:.*missing required fields"):
            list(read_tasks(io.StringIO(malformed)))


class PromptTests(unittest.TestCase):
    def test_prompt_contains_required_public_information_only(self):
        prompt = build_prompt(
            valid_task(),
            language_description="VISIBLE-LANGUAGE-SYNTAX",
            output_format="VISIBLE-OUTPUT-FORMAT",
        )
        for visible in (
            "VISIBLE-LANGUAGE-SYNTAX",
            "把输入原样输出：中文说明",
            '"input":""',
            '"output":""',
            "VISIBLE-OUTPUT-FORMAT",
        ):
            self.assertIn(visible, prompt)

        for private in (
            "hidden-input",
            "hidden-output",
            "secret-reference-program",
            "secret-metadata",
            "secret-limit",
            "secret-generator",
            "secret-template-family",
            "secret-standard-answer",
            "secret-signature",
            "identity",
            "unicode",
            "a" * 64,
            "b" * 64,
        ):
            self.assertNotIn(private, prompt)


class ReproducibilityTests(unittest.TestCase):
    def test_seeded_generator_is_reproducible(self):
        def generate(config, seed):
            rng = random.Random(seed)
            for _ in range(config["count"]):
                yield {"input": str(rng.randrange(100)), "output": ""}

        result = check_reproducible(generate, config={"count": 5}, seed=123)
        self.assertEqual(123, result.seed)
        self.assertEqual(5, result.record_count)
        self.assertEqual(64, len(result.sha256))

    def test_unstable_generator_is_rejected(self):
        calls = iter(("first", "second"))

        def generate(_config, _seed):
            return [{"value": next(calls)}]

        with self.assertRaises(ReproducibilityError):
            check_reproducible(generate, config={}, seed=1)

    def test_seed_must_be_explicit_integer(self):
        with self.assertRaises(TypeError):
            check_reproducible(lambda config, seed: [], config={}, seed=None)


if __name__ == "__main__":
    unittest.main()
