"""Canonical semantic and structural fingerprints with alpha renaming."""

import hashlib
import json


def _hash(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_characters(values, input_alphabet=()):
    input_set = set(input_alphabet)
    input_names = {}
    marker_names = {}

    def rename(char):
        table = input_names if char in input_set else marker_names
        prefix = "I" if char in input_set else "M"
        if char not in table:
            table[char] = "%s%d" % (prefix, len(table))
        return table[char]

    canonical = []
    for value in values:
        canonical.append(tuple(rename(char) for char in value))
    return canonical


def canonical_program(program, input_alphabet=()):
    """Canonicalize literal characters while preserving keywords and rule order."""
    pieces = []
    literals = []
    for line in program.splitlines():
        line_pieces = []
        index = 0
        while index < len(line):
            if line[index] == "(":
                end = line.find(")", index)
                if end >= 0:
                    line_pieces.append(("keyword", line[index : end + 1]))
                    index = end + 1
                    continue
            char = line[index]
            if char == "=":
                line_pieces.append(("equals", "="))
            else:
                literal_index = len(literals)
                literals.append(char)
                line_pieces.append(("literal", literal_index))
            index += 1
        pieces.append(line_pieces)

    renamed = _canonical_characters(literals, input_alphabet)
    canonical = []
    for line in pieces:
        rendered = []
        for kind, value in line:
            rendered.append(renamed[value][0] if kind == "literal" else value)
        canonical.append(rendered)
    return canonical


def structural_fingerprint(program, input_alphabet=()):
    return _hash(canonical_program(program, input_alphabet))


def semantic_fingerprint(outcomes, input_alphabet=()):
    """Hash behavior after canonical renaming of input/output symbols."""
    ordered = sorted(outcomes, key=lambda item: (len(item.input), item.input))
    values = []
    for outcome in ordered:
        values.append(outcome.input)
        values.append(outcome.output or "")
    renamed = _canonical_characters(values, input_alphabet)
    payload = []
    for index, outcome in enumerate(ordered):
        payload.append(
            {
                "input": renamed[index * 2],
                "output": renamed[index * 2 + 1],
                "terminating": outcome.terminating,
                "error": outcome.error,
            }
        )
    return _hash(payload)
