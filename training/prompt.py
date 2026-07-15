"""Prompt construction with an explicit public-field allowlist."""

import json

from .schema import SchemaValidationError, validate_task


def _required_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError("%s: expected a non-empty string" % name)
    return value


def build_prompt(task, language_description, output_format):
    """Build the model prompt from public information only.

    Private task fields are intentionally never interpolated here.  In
    particular, hidden tests, reference programs, generator information,
    template family, standard answer, metadata, limits, and behavior signature
    remain unavailable to the model.
    """
    validate_task(task)
    language_description = _required_text(
        language_description, "language_description"
    )
    output_format = _required_text(output_format, "output_format")

    public_tests = "\n".join(
        json.dumps(test_case, ensure_ascii=False, separators=(",", ":"))
        for test_case in task["public_tests"]
    )

    return "\n\n".join(
        (
            "A=B language and allowed syntax:\n" + language_description,
            "Task description:\n" + task["description"],
            "Public tests (JSONL, one object per line):\n" + public_tests,
            "Required output format:\n" + output_format,
        )
    )
