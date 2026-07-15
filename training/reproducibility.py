"""Helpers for checking seeded data generators."""

import copy
import hashlib
import json
from dataclasses import dataclass


class ReproducibilityError(AssertionError):
    """Raised when two runs with the same config and seed differ."""


@dataclass(frozen=True)
class ReproducibilityResult:
    seed: int
    record_count: int
    sha256: str


def _validate_seed(seed):
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")


def _run(generator, config, seed):
    result = generator(copy.deepcopy(config), seed)
    return list(result)


def _canonical_bytes(records):
    return json.dumps(
        records,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def check_reproducible(generator, *, config, seed):
    """Run ``generator(config, seed)`` twice and compare canonical output."""
    _validate_seed(seed)
    first = _run(generator, config, seed)
    second = _run(generator, config, seed)
    try:
        first_bytes = _canonical_bytes(first)
        second_bytes = _canonical_bytes(second)
    except (TypeError, ValueError) as error:
        raise ReproducibilityError(
            "generator output must contain strict JSON-compatible values"
        ) from error

    if first_bytes != second_bytes:
        raise ReproducibilityError(
            "generator output changed for identical config and seed %d" % seed
        )

    return ReproducibilityResult(
        seed=seed,
        record_count=len(first),
        sha256=hashlib.sha256(first_bytes).hexdigest(),
    )
