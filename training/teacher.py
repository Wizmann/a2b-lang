"""Teacher provider adapters, caching, extraction, verification, and repair."""

import hashlib
import json
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from A2B import A2BParseException, parse

from .dataset import (
    InputPoolConfig,
    build_input_pool,
    execute_with_limits,
)
from .prompt import build_prompt


@dataclass(frozen=True)
class TeacherRoles:
    primary: str = "gpt-5.6-terra"
    fast_candidate: str = "gpt-5.6-luna"
    repair: str = "gpt-5.3-codex"
    judge: str = "gpt-5.6-sol"


@dataclass(frozen=True)
class CandidateVerification:
    syntax_ok: bool
    line_limit_ok: bool
    public_solved: bool
    hidden_solved: bool
    failure_stage: str = None
    public_counterexample: dict = None

    @property
    def verified(self):
        return (
            self.syntax_ok
            and self.line_limit_ok
            and self.public_solved
            and self.hidden_solved
        )


@dataclass(frozen=True)
class TeacherAttempt:
    model: str
    candidate: str
    extracted: bool
    cached: bool
    verification: CandidateVerification
    disclosed_counterexample: dict = None


@dataclass(frozen=True)
class TeacherResult:
    solved: bool
    program: str = None
    attempts: tuple = ()


class TeacherProvider:
    name = None

    def complete(self, model, messages):
        raise NotImplementedError


class OpenAICompatibleProvider(TeacherProvider):
    name = "openai_compatible"

    def __init__(self, base_url, *, timeout=180, api_key=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    def complete(self, model, messages):
        payload = json.dumps(
            {"model": model, "messages": list(messages)}, ensure_ascii=False
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            raise RuntimeError("teacher HTTP %d: %s" % (error.code, detail)) from error
        return body["choices"][0]["message"]["content"]


class MockTeacherProvider(TeacherProvider):
    name = "mock"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, model, messages):
        self.calls.append({"model": model, "messages": list(messages)})
        if not self.responses:
            raise RuntimeError("mock response queue is empty")
        return self.responses.pop(0)


class TeacherCache:
    def __init__(self, directory):
        self.directory = Path(directory)

    @staticmethod
    def key(provider_name, model, messages):
        payload = json.dumps(
            {
                "provider": provider_name,
                "model": model,
                "messages": list(messages),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def get(self, key):
        path = self.directory / (key + ".json")
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["content"]

    def put(self, key, content):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / (key + ".json")
        path.write_text(
            json.dumps({"content": content}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def extract_candidate(content):
    match = re.search(r"<program>\s*(.*?)\s*</program>", content, re.I | re.S)
    if match:
        return match.group(1).strip("\n"), True
    fences = re.findall(r"```(?:a2b|text)?\s*\n(.*?)```", content, re.I | re.S)
    if fences:
        return fences[-1].strip("\n"), True
    return content.strip(), False


def _check_cases(program, cases, max_length):
    for case in cases:
        outcome = execute_with_limits(
            program,
            case["input"],
            max_steps=10000,
            max_length=max_length,
        )
        if not outcome.terminating or outcome.output != case["output"]:
            return False, dict(case)
    return True, None


def verify_candidate(source, problem):
    generated = problem.generated_program
    line_ok = len(source.splitlines()) <= generated.limits["max_program_lines"]
    if not line_ok:
        return CandidateVerification(True, False, False, False, "line_limit")
    character_ok = (
        len(source) <= generated.limits["max_program_characters"]
    )
    if not character_ok:
        return CandidateVerification(True, False, False, False, "character_limit")
    try:
        program = parse(source)
    except A2BParseException:
        return CandidateVerification(False, False, False, False, "syntax")
    public_ok, public_failure = _check_cases(
        program, problem.public_tests, generated.limits["max_string_length"]
    )
    if not public_ok:
        return CandidateVerification(
            True, True, False, False, "public", public_failure
        )
    hidden_ok, _ = _check_cases(
        program, problem.hidden_tests, generated.limits["max_string_length"]
    )
    return CandidateVerification(
        True,
        True,
        True,
        hidden_ok,
        None if hidden_ok else "hidden",
    )


def _teacher_messages(prompt, repair_feedback=None):
    messages = [
        {
            "role": "system",
            "content": (
                "Solve the A=B task. Output only <program>...</program>; "
                "do not reveal analysis."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    if repair_feedback:
        messages.append(
            {
                "role": "user",
                "content": (
                    "The candidate failed this newly disclosed verifier case: "
                    + json.dumps(repair_feedback, ensure_ascii=False)
                    + "\nReturn a corrected program."
                ),
            }
        )
    return tuple(messages)


def _fresh_counterexample(problem, candidate, seed):
    """Find a new reference-derived case without disclosing reserved hidden tests."""
    try:
        candidate_program = parse(candidate)
        reference_program = parse(problem.generated_program.program)
    except A2BParseException:
        return None
    rng = random.Random(seed)
    generated = problem.generated_program
    pool = build_input_pool(
        rng,
        generated,
        InputPoolConfig(pool_size=256, exhaustive_max_length=4),
    )
    reserved = {
        case["input"] for case in problem.public_tests + problem.hidden_tests
    }
    for input_value in pool:
        if input_value in reserved:
            continue
        reference = execute_with_limits(
            reference_program,
            input_value,
            max_steps=10000,
            max_length=generated.limits["max_string_length"],
        )
        candidate_result = execute_with_limits(
            candidate_program,
            input_value,
            max_steps=10000,
            max_length=generated.limits["max_string_length"],
        )
        if reference.terminating and (
            not candidate_result.terminating
            or candidate_result.output != reference.output
        ):
            return {"input": input_value, "output": reference.output}
    return None


class TeacherPipeline:
    def __init__(self, provider, *, roles=None, cache=None):
        self.provider = provider
        self.roles = roles or TeacherRoles()
        self.cache = cache

    def _complete(self, model, messages):
        key = None
        if self.cache is not None:
            key = self.cache.key(self.provider.name, model, messages)
            cached = self.cache.get(key)
            if cached is not None:
                return cached, True
        content = self.provider.complete(model, messages)
        if self.cache is not None:
            self.cache.put(key, content)
        return content, False

    def solve(self, problem, language_description, output_format, *, max_repairs=1,
              repair_seed=0):
        task = problem.to_task_record()
        prompt = build_prompt(task, language_description, output_format)
        attempts = []
        feedback = None

        models = [self.roles.primary] + [self.roles.repair] * max_repairs
        for index, model in enumerate(models):
            messages = _teacher_messages(prompt, feedback)
            content, cached = self._complete(model, messages)
            candidate, extracted = extract_candidate(content)
            verification = verify_candidate(candidate, problem)
            disclosed = feedback
            attempts.append(
                TeacherAttempt(
                    model=model,
                    candidate=candidate,
                    extracted=extracted,
                    cached=cached,
                    verification=verification,
                    disclosed_counterexample=disclosed,
                )
            )
            if verification.verified:
                return TeacherResult(True, candidate, tuple(attempts))

            if verification.public_counterexample is not None:
                # Public examples were already visible in the original prompt.
                feedback = verification.public_counterexample
            elif verification.public_solved and not verification.hidden_solved:
                feedback = _fresh_counterexample(
                    problem, candidate, repair_seed + index
                )
            else:
                feedback = None

        return TeacherResult(False, None, tuple(attempts))
