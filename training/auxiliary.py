"""Locally labelled auxiliary tasks for execution and program reasoning."""

import random

from A2B import EXECUTED_DONE, EXECUTED_NONE, EXECUTED_RETURN, parse

from .dataset import execute_with_limits


def bounded_trace(source, input_value, *, step_limit, length_limit):
    program = parse(source)
    for expression in program.exprs:
        expression.executed = 0
    value = input_value
    trace = []
    if len(value) > length_limit:
        return {"status": "length_limit", "output": None, "trace": trace}
    while True:
        executed = EXECUTED_NONE
        for expression in program.exprs:
            executed, output = expression.Execute(value)
            if executed in (EXECUTED_DONE, EXECUTED_RETURN):
                trace.append(
                    {
                        "step": len(trace) + 1,
                        "rule_line": expression.line_no + 1,
                        "rule": expression.plain_text,
                        "before": value,
                        "after": output,
                    }
                )
                value = output
                break
        else:
            return {"status": "halted", "output": value, "trace": trace}
        if len(trace) > step_limit:
            return {"status": "step_limit", "output": None, "trace": trace}
        if len(value) > length_limit:
            return {"status": "length_limit", "output": None, "trace": trace}
        if executed == EXECUTED_RETURN:
            return {"status": "halted", "output": value, "trace": trace}


def _cases(problem):
    return tuple(problem.public_tests) + tuple(problem.hidden_tests)


def _counterexample(left_source, right_source, cases, max_length):
    left, right = parse(left_source), parse(right_source)
    for case in cases:
        left_result = execute_with_limits(
            left, case["input"], max_steps=2000, max_length=max_length
        )
        right_result = execute_with_limits(
            right, case["input"], max_steps=2000, max_length=max_length
        )
        if (
            left_result.terminating != right_result.terminating
            or left_result.output != right_result.output
        ):
            return {
                "input": case["input"],
                "left_output": left_result.output,
                "right_output": right_result.output,
            }
    return None


def _wrong_program(source):
    lines = source.splitlines()
    if len(lines) > 1:
        return "\n".join(lines[:-1])
    return ""


def generate_auxiliary_tasks(
    problems, *, seed, per_problem=1, split_by_problem=None
):
    rng = random.Random(seed)
    problems = tuple(problems)
    problem_by_id = {problem.id: problem for problem in problems}
    split_by_problem = dict(split_by_problem or {})
    records = {
        "execution": [],
        "trace": [],
        "repair": [],
        "completion": [],
        "ordering": [],
        "bounded_termination": [],
        "finite_domain_equivalence": [],
        "distinguishing_input": [],
    }
    for problem in problems:
        source = problem.generated_program.program
        cases = list(_cases(problem))
        rng.shuffle(cases)
        max_length = problem.generated_program.limits["max_string_length"]
        for case in cases[:per_problem]:
            result = bounded_trace(
                source,
                case["input"],
                step_limit=2000,
                length_limit=max_length,
            )
            records["execution"].append(
                {
                    "problem_id": problem.id,
                    "program": source,
                    "input": case["input"],
                    "output": result["output"],
                }
            )
            records["trace"].append(
                {
                    "problem_id": problem.id,
                    "program": source,
                    "input": case["input"],
                    "status": result["status"],
                    "trace": result["trace"],
                }
            )
            records["bounded_termination"].append(
                {
                    "problem_id": problem.id,
                    "program": source,
                    "input": case["input"],
                    "step_limit": 2000,
                    "length_limit": max_length,
                    "label": result["status"],
                }
            )

        wrong = _wrong_program(source)
        counterexample = _counterexample(wrong, source, cases, max_length)
        if counterexample is not None:
            records["repair"].append(
                {
                    "problem_id": problem.id,
                    "description": problem.generated_program.description,
                    "public_tests": list(problem.public_tests),
                    "wrong_program": wrong,
                    "counterexample": {
                        "input": counterexample["input"],
                        "output": counterexample["right_output"],
                    },
                    "fixed_program": source,
                }
            )
            domain = [case["input"] for case in cases]
            records["finite_domain_equivalence"].append(
                {
                    "problem_id": problem.id,
                    "program_a": wrong,
                    "program_b": source,
                    "domain": domain,
                    "label": False,
                }
            )
            records["distinguishing_input"].append(
                {
                    "problem_id": problem.id,
                    "program_a": wrong,
                    "program_b": source,
                    "input": counterexample["input"],
                    "output_a": counterexample["left_output"],
                    "output_b": counterexample["right_output"],
                }
            )

        lines = source.splitlines()
        if len(lines) > 1:
            missing_index = rng.randrange(len(lines))
            incomplete = list(lines)
            missing_rule = incomplete[missing_index]
            incomplete[missing_index] = "<MISSING_RULE>"
            records["completion"].append(
                {
                    "problem_id": problem.id,
                    "description": problem.generated_program.description,
                    "public_tests": list(problem.public_tests),
                    "incomplete_program": "\n".join(incomplete),
                    "missing_rule_index": missing_index,
                    "missing_rule": missing_rule,
                }
            )
            shuffled = list(lines)
            rng.shuffle(shuffled)
            shuffled_source = "\n".join(shuffled)
            if shuffled_source != source:
                difference = _counterexample(
                    shuffled_source, source, cases, max_length
                )
                if difference is not None:
                    records["ordering"].append(
                        {
                            "problem_id": problem.id,
                            "description": problem.generated_program.description,
                            "public_tests": list(problem.public_tests),
                            "shuffled_rules": shuffled,
                            "ordered_program": source,
                        }
                    )

        records["finite_domain_equivalence"].append(
            {
                "problem_id": problem.id,
                "program_a": source,
                "program_b": source,
                "domain": [case["input"] for case in cases],
                "label": True,
            }
        )

    # Explicit local limit labels ensure all three termination classes occur.
    records["bounded_termination"].extend(
        (
            {
                "problem_id": "synthetic_termination_step_limit",
                "program": "a=a",
                "input": "a",
                "step_limit": 4,
                "length_limit": 10,
                "label": bounded_trace("a=a", "a", step_limit=4, length_limit=10)["status"],
            },
            {
                "problem_id": "synthetic_termination_length_limit",
                "program": "a=aa",
                "input": "a",
                "step_limit": 100,
                "length_limit": 4,
                "label": bounded_trace("a=aa", "a", step_limit=100, length_limit=4)["status"],
            },
        )
    )
    for values in records.values():
        for record in values:
            problem_id = record["problem_id"]
            problem = problem_by_id.get(problem_id)
            if problem is None:
                record.update(
                    {
                        "root_problem_id": problem_id,
                        "program_lineage_id": "program:" + problem_id,
                        "mutant_family_id": "mutant:" + problem_id,
                        "alpha_equivalence_class": "synthetic:" + problem_id,
                        "split": "train",
                    }
                )
                continue
            hardening = problem.hardening
            record.update(
                {
                    "root_problem_id": hardening.get(
                        "root_problem_id", problem.id
                    ),
                    "program_lineage_id": hardening.get(
                        "program_lineage_id", "program:" + problem.id
                    ),
                    "mutant_family_id": hardening.get(
                        "mutant_family_id", "mutant:" + problem.id
                    ),
                    "alpha_equivalence_class": hardening.get(
                        "alpha_equivalence_class",
                        problem.structural_fingerprint,
                    ),
                    "split": split_by_problem.get(problem.id, "train"),
                }
            )
    return {name: tuple(values) for name, values in records.items()}
