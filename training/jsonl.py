"""Line-oriented, UTF-8 JSONL I/O with optional runtime validation."""

import json
import os
from pathlib import Path

from .schema import validate_task


class JsonlError(ValueError):
    """Raised for malformed JSONL or a record that fails validation."""

    def __init__(self, source, line_number, message):
        self.source = source
        self.line_number = line_number
        super().__init__("%s:%d: %s" % (source, line_number, message))


def _is_path(value):
    return isinstance(value, (str, bytes, os.PathLike))


def read_jsonl(source, validator=None):
    """Yield one decoded value per physical line.

    Blank lines are rejected.  Empty strings inside a JSON record remain valid
    values.  ``validator`` is called for every decoded value when supplied.
    """
    should_close = _is_path(source)
    input_file = Path(source).open("r", encoding="utf-8") if should_close else source
    source_name = str(source) if should_close else getattr(source, "name", "<stream>")

    try:
        for line_number, line in enumerate(input_file, 1):
            if not line.strip():
                raise JsonlError(source_name, line_number, "blank lines are not allowed")
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise JsonlError(source_name, line_number, str(error)) from error
            if validator is not None:
                try:
                    record = validator(record)
                except (TypeError, ValueError) as error:
                    raise JsonlError(source_name, line_number, str(error)) from error
            yield record
    finally:
        if should_close:
            input_file.close()


def write_jsonl(destination, records, validator=None):
    """Write records as compact UTF-8 JSON, one record per line."""
    should_close = _is_path(destination)
    output_file = (
        Path(destination).open("w", encoding="utf-8", newline="\n")
        if should_close
        else destination
    )
    destination_name = (
        str(destination)
        if should_close
        else getattr(destination, "name", "<stream>")
    )

    try:
        for line_number, record in enumerate(records, 1):
            if validator is not None:
                try:
                    record = validator(record)
                except (TypeError, ValueError) as error:
                    raise JsonlError(destination_name, line_number, str(error)) from error
            try:
                encoded = json.dumps(
                    record,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
            except (TypeError, ValueError) as error:
                raise JsonlError(destination_name, line_number, str(error)) from error
            output_file.write(encoded + "\n")
    finally:
        if should_close:
            output_file.close()


def read_tasks(source):
    """Read and validate Stage A task records."""
    return read_jsonl(source, validator=validate_task)


def write_tasks(destination, records):
    """Validate and write Stage A task records."""
    write_jsonl(destination, records, validator=validate_task)
