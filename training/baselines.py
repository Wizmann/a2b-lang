"""Small deterministic, non-neural baselines for generated A=B problems."""

from dataclasses import dataclass

from A2B import A2BParseException, parse

from .dataset import execute_with_limits


@dataclass(frozen=True)
class BaselineProblem:
    description: str
    public_tests: tuple
    max_program_lines: int
    max_program_characters: int
    max_string_length: int


@dataclass(frozen=True)
class BaselineResult:
    baseline: str
    attempted: int
    public_solved: int
    hidden_solved: int
    public_only_overfit: int


class Baseline:
    name = None

    def candidates(self, problem):
        raise NotImplementedError

    def solve(self, problem):
        for candidate in self.candidates(problem):
            if _passes(candidate, problem.public_tests, problem):
                return candidate
        return None


def _view(problem):
    return BaselineProblem(
        description=problem.generated_program.description,
        public_tests=problem.public_tests,
        max_program_lines=problem.generated_program.limits["max_program_lines"],
        max_program_characters=problem.generated_program.limits[
            "max_program_characters"
        ],
        max_string_length=problem.generated_program.limits["max_string_length"],
    )


def _passes(source, cases, problem):
    if len(source.splitlines()) > problem.max_program_lines:
        return False
    if len(source) > problem.max_program_characters:
        return False
    try:
        program = parse(source)
    except A2BParseException:
        return False
    for case in cases:
        outcome = execute_with_limits(
            program,
            case["input"],
            max_steps=10000,
            max_length=problem.max_string_length,
        )
        if not outcome.terminating or outcome.output != case["output"]:
            return False
    return True


class IdentityBaseline(Baseline):
    name = "identity"

    def candidates(self, problem):
        return ("",)


class ConstantBaseline(Baseline):
    name = "constant"

    def candidates(self, problem):
        outputs = sorted({case["output"] for case in problem.public_tests})
        return tuple("=(return)%s" % output for output in outputs)


def _observed_characters(problem):
    return tuple(
        sorted(
            {
                char
                for case in problem.public_tests
                for value in (case["input"], case["output"])
                for char in value
                if ord(char) < 128 and char not in "=#()"
            }
        )
    )


class SingleRuleBaseline(Baseline):
    name = "single_rule_search"

    def candidates(self, problem):
        chars = _observed_characters(problem)
        candidates = []
        for left in chars:
            for right in ("",) + chars:
                if left != right:
                    candidates.append("%s=%s" % (left, right))
        for char in chars:
            candidates.extend(
                (
                    "(start)%s=" % char,
                    "(end)%s=" % char,
                    "%s=(return)true\n=(return)false" % char,
                )
            )
        return tuple(candidates)


class TemplateSearchBaseline(Baseline):
    name = "template_search"

    def candidates(self, problem):
        chars = _observed_characters(problem)
        candidates = []
        for char in chars:
            candidates.append("(start)%s=\n(end)%s=" % (char, char))
            for count in range(1, 5):
                candidates.append("\n".join("(once)%s=" % char for _ in range(count)))
        for marker in ("X", "Y", "Z"):
            candidates.append(
                "\n".join(
                    (
                        "(once)=(end)%s" % marker,
                        "0%s=1" % marker,
                        "1%s=%s0" % (marker, marker),
                        "%s=1" % marker,
                    )
                )
            )
        return tuple(candidates)


DEFAULT_BASELINES = (
    IdentityBaseline(),
    ConstantBaseline(),
    SingleRuleBaseline(),
    TemplateSearchBaseline(),
)


def run_baselines(problems, baselines=DEFAULT_BASELINES):
    results = []
    for baseline in baselines:
        attempted = public_solved = hidden_solved = public_only = 0
        for problem in problems:
            attempted += 1
            view = _view(problem)
            candidate = baseline.solve(view)
            if candidate is None:
                continue
            public_solved += 1
            hidden_ok = _passes(candidate, problem.hidden_tests, view)
            if hidden_ok:
                hidden_solved += 1
            else:
                public_only += 1
        results.append(
            BaselineResult(
                baseline=baseline.name,
                attempted=attempted,
                public_solved=public_solved,
                hidden_solved=hidden_solved,
                public_only_overfit=public_only,
            )
        )
    return tuple(results)
