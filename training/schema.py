"""Runtime schema validation for Stage A task records.

The schema deliberately keeps prompt-visible and private fields in the same
record.  ``training.prompt`` is responsible for selecting the small, public
subset that a model may see.
"""

import math


class SchemaValidationError(ValueError):
    """Raised when a value does not match the Stage A runtime schema."""


REQUIRED_TASK_FIELDS = {
    "description",
    "public_tests",
    "hidden_tests",
    "reference_programs",
    "metadata",
    "concepts",
    "task_domain",
    "algorithm_family",
    "composition_depth",
    "required_features",
    "description_style",
    "source_type",
    "semantic_fingerprint",
    "structural_fingerprint",
}

OPTIONAL_TASK_FIELDS = {
    "id",
    "limits",
    "generator",
    "template_family",
    "standard_answer",
    "behavior_signature",
    "declared_composition_depth",
    "effective_composition_depth",
    "effective_components",
    "dead_components",
    "component_interaction",
    "order_sensitive",
    "order_distinguishing_input",
    "order_comparison",
    "order_outputs",
    "reducible_to_single_stage",
    "normalized_semantic_ir",
    "genuine_composition",
    "superficial_composition",
    "specification_level",
    "solution_revealing_score",
    "concrete_behavior_fingerprint",
    "alpha_normalized_behavior_fingerprint",
    "semantic_ir_fingerprint",
    "ontology_errors",
    "root_problem_id",
    "program_lineage_id",
    "mutant_family_id",
    "alpha_equivalence_class",
    "construction_domain",
    "public_domain",
    "hidden_domain",
    "generalization_domain",
    "audit_domain",
    "audit_reference_verification",
    "cognitive_family",
    "semantic_archetype",
    "parameter_instance",
    "information_scope",
    "memory_model",
    "traversal_model",
    "output_shape",
    "primary_invariant",
    "cognitive_signature",
    "composition_component_probe",
}

COGNITIVE_REQUIRED_FIELDS = {
    "cognitive_family",
    "semantic_archetype",
    "parameter_instance",
    "information_scope",
    "memory_model",
    "traversal_model",
    "output_shape",
    "primary_invariant",
    "cognitive_signature",
}

HARDENING_REQUIRED_FIELDS = {
    "declared_composition_depth",
    "effective_composition_depth",
    "effective_components",
    "dead_components",
    "component_interaction",
    "order_sensitive",
    "reducible_to_single_stage",
    "normalized_semantic_ir",
    "specification_level",
    "solution_revealing_score",
    "concrete_behavior_fingerprint",
    "alpha_normalized_behavior_fingerprint",
    "semantic_ir_fingerprint",
    "ontology_errors",
    "root_problem_id",
    "program_lineage_id",
    "mutant_family_id",
    "alpha_equivalence_class",
    "construction_domain",
    "public_domain",
    "hidden_domain",
    "generalization_domain",
    "audit_domain",
    "audit_reference_verification",
}


def _fail(path, message):
    raise SchemaValidationError("%s: %s" % (path, message))


def _require_string(value, path, allow_empty=True):
    if not isinstance(value, str):
        _fail(path, "expected a string")
    if not allow_empty and not value:
        _fail(path, "must not be empty")


def _validate_json_value(value, path):
    """Reject values that cannot be represented by strict JSON."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail(path, "non-finite floats are not valid JSON")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, "%s[%d]" % (path, index))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail(path, "JSON object keys must be strings")
            _validate_json_value(item, "%s.%s" % (path, key))
        return
    _fail(path, "expected a JSON-compatible value")


def _validate_test_case(value, path):
    if not isinstance(value, dict):
        _fail(path, "expected an object")
    if set(value) != {"input", "output"}:
        _fail(path, "expected exactly the fields 'input' and 'output'")
    _require_string(value["input"], path + ".input")
    _require_string(value["output"], path + ".output")


def _validate_tests(value, path, require_nonempty):
    if not isinstance(value, list):
        _fail(path, "expected an array")
    if require_nonempty and not value:
        _fail(path, "must contain at least one test")
    for index, test_case in enumerate(value):
        _validate_test_case(test_case, "%s[%d]" % (path, index))


def validate_task(record):
    """Validate and return one Stage A task record.

    Unknown fields are rejected so misspellings and accidentally unclassified
    private data cannot silently enter the pipeline.
    """
    if not isinstance(record, dict):
        _fail("task", "expected an object")

    fields = set(record)
    missing = REQUIRED_TASK_FIELDS - fields
    if missing:
        _fail("task", "missing required fields: %s" % ", ".join(sorted(missing)))

    unknown = fields - REQUIRED_TASK_FIELDS - OPTIONAL_TASK_FIELDS
    if unknown:
        _fail("task", "unknown fields: %s" % ", ".join(sorted(unknown)))

    _require_string(record["description"], "task.description", allow_empty=False)
    for field_name in ("concepts", "required_features"):
        values = record[field_name]
        if not isinstance(values, list):
            _fail("task." + field_name, "expected an array")
        if field_name == "concepts" and not values:
            _fail("task.concepts", "must contain at least one concept")
        for index, value in enumerate(values):
            _require_string(
                value,
                "task.%s[%d]" % (field_name, index),
                allow_empty=False,
            )
    for field_name in (
        "task_domain",
        "algorithm_family",
        "description_style",
    ):
        _require_string(record[field_name], "task." + field_name, allow_empty=False)
    for field_name in ("semantic_fingerprint", "structural_fingerprint"):
        value = record[field_name]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            _fail("task." + field_name, "expected a lowercase SHA-256 hex digest")
    if (
        isinstance(record["composition_depth"], bool)
        or not isinstance(record["composition_depth"], int)
        or not 1 <= record["composition_depth"] <= 3
    ):
        _fail("task.composition_depth", "expected an integer from 1 to 3")
    if not isinstance(record["source_type"], str) or record["source_type"] not in {
        "template",
        "composed",
        "enumerated",
        "random_mined",
        "teacher",
        "handwritten",
    }:
        _fail("task.source_type", "invalid source type")
    _validate_tests(record["public_tests"], "task.public_tests", require_nonempty=True)
    _validate_tests(record["hidden_tests"], "task.hidden_tests", require_nonempty=False)

    references = record["reference_programs"]
    if not isinstance(references, list):
        _fail("task.reference_programs", "expected an array")
    if not references:
        _fail("task.reference_programs", "must contain at least one program")
    for index, program in enumerate(references):
        _require_string(
            program,
            "task.reference_programs[%d]" % index,
            allow_empty=False,
        )

    if not isinstance(record["metadata"], dict):
        _fail("task.metadata", "expected an object")
    _validate_json_value(record["metadata"], "task.metadata")

    if "id" in record:
        _require_string(record["id"], "task.id", allow_empty=False)
    if "limits" in record:
        if not isinstance(record["limits"], dict):
            _fail("task.limits", "expected an object")
        _validate_json_value(record["limits"], "task.limits")
    if "generator" in record:
        if not isinstance(record["generator"], dict):
            _fail("task.generator", "expected an object")
        _validate_json_value(record["generator"], "task.generator")
    if "template_family" in record:
        _require_string(
            record["template_family"],
            "task.template_family",
            allow_empty=False,
        )
    if "standard_answer" in record:
        _require_string(record["standard_answer"], "task.standard_answer")
    if "behavior_signature" in record:
        _validate_json_value(record["behavior_signature"], "task.behavior_signature")

    return record


def validate_hardened_task(record):
    """验证语义加固记录的附加约束。"""
    validate_task(record)
    missing = HARDENING_REQUIRED_FIELDS - set(record)
    if missing:
        _fail(
            "task",
            "missing hardening fields: %s" % ", ".join(sorted(missing)),
        )
    for name in ("declared_composition_depth", "effective_composition_depth"):
        value = record[name]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 3:
            _fail("task." + name, "expected an integer from 1 to 3")
    if record["declared_composition_depth"] != record["composition_depth"]:
        _fail("task.declared_composition_depth", "must equal composition_depth")
    for name in ("effective_components", "dead_components"):
        value = record[name]
        if not isinstance(value, list) or not all(
            isinstance(index, int) and not isinstance(index, bool) and index >= 0
            for index in value
        ):
            _fail("task." + name, "expected a list of non-negative indices")
    if len(record["effective_components"]) != record["effective_composition_depth"]:
        _fail("task.effective_components", "count must match effective depth")
    for name in (
        "order_sensitive",
        "reducible_to_single_stage",
        "genuine_composition",
        "superficial_composition",
    ):
        if name in record and not isinstance(record[name], bool):
            _fail("task." + name, "expected a boolean")
    if record["specification_level"] not in {"functional", "io_only", "operational"}:
        _fail("task.specification_level", "invalid specification level")
    score = record["solution_revealing_score"]
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
        _fail("task.solution_revealing_score", "expected a number from 0 to 1")
    for name in (
        "concrete_behavior_fingerprint",
        "alpha_normalized_behavior_fingerprint",
        "semantic_ir_fingerprint",
        "alpha_equivalence_class",
    ):
        value = record[name]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            _fail("task." + name, "expected a lowercase SHA-256 hex digest")
    for name in ("root_problem_id", "program_lineage_id", "mutant_family_id"):
        _require_string(record[name], "task." + name, allow_empty=False)
    if not isinstance(record["ontology_errors"], list) or not all(
        isinstance(value, str) and value for value in record["ontology_errors"]
    ):
        _fail("task.ontology_errors", "expected a list of error names")
    if not isinstance(record["normalized_semantic_ir"], dict):
        _fail("task.normalized_semantic_ir", "expected an object")
    _validate_json_value(record["normalized_semantic_ir"], "task.normalized_semantic_ir")
    for name in (
        "construction_domain",
        "public_domain",
        "hidden_domain",
        "generalization_domain",
        "audit_domain",
    ):
        domain = record[name]
        if not isinstance(domain, dict):
            _fail("task." + name, "expected an object")
        for bound in ("min_length", "max_length"):
            value = domain.get(bound)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                _fail("task.%s.%s" % (name, bound), "expected a non-negative integer")
        if domain["max_length"] < domain["min_length"]:
            _fail("task." + name, "maximum is smaller than minimum")
    return record


def validate_cognitive_task(record):
    """Validate one cognitive-diversity review-smoke synthesis record."""
    validate_hardened_task(record)
    missing = COGNITIVE_REQUIRED_FIELDS - set(record)
    if missing:
        _fail(
            "task",
            "missing cognitive fields: %s" % ", ".join(sorted(missing)),
        )
    for name in COGNITIVE_REQUIRED_FIELDS - {"parameter_instance"}:
        _require_string(record[name], "task." + name, allow_empty=False)
    value = record["parameter_instance"]
    if not isinstance(value, dict):
        _fail("task.parameter_instance", "expected an object")
    _validate_json_value(value, "task.parameter_instance")
    if record["composition_depth"] > 1:
        probe = record.get("composition_component_probe")
        if not isinstance(probe, dict):
            _fail(
                "task.composition_component_probe",
                "composed tasks require a component probe",
            )
        if not probe.get("all_components_effective"):
            _fail(
                "task.composition_component_probe",
                "all components must be effective",
            )
    return record
