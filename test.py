#!/usr/bin/env python3

import sys
import unittest
from io import StringIO

import A2B
from A2B import A2BExecutionException, A2BParseException, execute, parse

def rules(*lines):
    return "\n".join(lines)


class ExecutionModelTests(unittest.TestCase):
    def test_empty_program_is_identity(self):
        program = parse("")
        for value in ("", "abc", " ()=#$^ "):
            self.assertEqual(value, execute(program, value))

    def test_plain_rule_replaces_all_occurrences_over_multiple_steps(self):
        program = parse("a=b")
        self.assertEqual("bbc", execute(program, "abc"))
        self.assertEqual("bbb", execute(program, "aab"))
        self.assertEqual("bbbbbc", execute(program, "aabbac"))

    def test_each_step_restarts_rule_scan_from_the_top(self):
        program = parse(rules("a=b", "ba=x"))
        self.assertEqual("bb", execute(program, "aa"))

    def test_first_applicable_rule_has_priority(self):
        program = parse(rules("a=x", "a=y", "x="))
        self.assertEqual("", execute(program, "a"))

    def test_replacement_uses_leftmost_match(self):
        program = parse("ab=X")
        stderr = StringIO()
        original_stderr = sys.stderr
        try:
            sys.stderr = stderr
            self.assertEqual("XX", execute(program, "abab", verbose=True))
        finally:
            sys.stderr = original_stderr
        trace = stderr.getvalue()
        self.assertIn("Step 1:", trace)
        self.assertIn("Step 2:", trace)
        self.assertNotIn("Step 3:", trace)

    def test_empty_patterns_match(self):
        self.assertEqual("ok", execute(parse("=(return)ok"), "anything"))
        self.assertEqual("Xab", execute(parse("(once)=(start)X"), "ab"))
        self.assertEqual("abX", execute(parse("(once)=(end)X"), "ab"))

    def test_blank_program_and_blank_input(self):
        self.assertEqual("", execute(parse("\n\n"), ""))


class KeywordTests(unittest.TestCase):
    def test_return_discards_current_state_and_halts(self):
        program = parse(rules("a=x", "x=(return)done", "x=wrong"))
        self.assertEqual("done", execute(program, "cat"))
        self.assertEqual("", execute(parse("=(return)"), "abc"))

    def test_start_on_left_only_matches_a_prefix(self):
        program = parse("(start)a=X")
        self.assertEqual("Xba", execute(program, "aba"))
        self.assertEqual("ba", execute(program, "ba"))

    def test_end_on_left_only_matches_a_suffix(self):
        program = parse("(end)a=X")
        self.assertEqual("abX", execute(program, "aba"))
        self.assertEqual("ab", execute(program, "ab"))

    def test_start_on_right_moves_replacement_to_prefix(self):
        self.assertEqual("Xac", execute(parse("b=(start)X"), "abc"))

    def test_end_on_right_moves_replacement_to_suffix(self):
        self.assertEqual("acX", execute(parse("b=(end)X"), "abc"))

    def test_keywords_on_both_sides_combine(self):
        self.assertEqual("bcX", execute(parse("(start)a=(end)X"), "abc"))
        self.assertEqual("Xab", execute(parse("(end)c=(start)X"), "abc"))

    def test_once_rule_executes_at_most_once(self):
        program = parse(rules("(once)a=aa", "a=b"))
        self.assertEqual("bb", execute(program, "a"))

    def test_once_is_not_consumed_until_the_rule_matches(self):
        program = parse(rules("(once)aa=x", "b=a"))
        self.assertEqual("x", execute(program, "ba"))

    def test_once_state_resets_for_each_execute_call(self):
        program = parse(rules("(once)a=x", "x=y"))
        self.assertEqual("y", execute(program, "a"))
        self.assertEqual("y", execute(program, "a"))


class CharacterAndWhitespaceTests(unittest.TestCase):
    def test_caret_and_dollar_are_ordinary_characters(self):
        program = parse(rules("^=A", "$=B"))
        self.assertEqual("AxB", execute(program, "^x$"))

    def test_input_whitespace_is_preserved(self):
        value = " \tabc  "
        self.assertEqual(value, execute(parse(""), value))

    def test_spaces_in_rule_patterns_are_significant(self):
        self.assertEqual("x", execute(parse(" a=x"), " a"))
        self.assertEqual(" ", execute(parse("a= "), "a"))

    def test_non_ascii_program_text_is_rejected(self):
        with self.assertRaises(A2BParseException):
            parse("a=中")

    def test_non_ascii_or_multiline_input_is_rejected(self):
        program = parse("")
        for value in ("中文", "a\nb", "a\rb"):
            with self.assertRaises(A2BExecutionException):
                execute(program, value)


class SyntaxTests(unittest.TestCase):
    def assert_parse_error(self, source):
        with self.assertRaises(A2BParseException):
            parse(source)

    def test_each_nonempty_line_has_exactly_one_equals_sign(self):
        self.assert_parse_error("abc")
        self.assert_parse_error("a=b=c")

    def test_unknown_or_malformed_keywords_are_rejected(self):
        self.assert_parse_error("(foo)a=b")
        self.assert_parse_error("(starta=b")
        self.assert_parse_error("(once)(start)a=b")

    def test_keyword_placement_is_checked(self):
        self.assert_parse_error("(return)a=b")
        self.assert_parse_error("a=(once)b")

    def test_parentheses_cannot_be_literal_pattern_text(self):
        self.assert_parse_error("a(b=c")
        self.assert_parse_error("a=b)c")

    def test_each_side_accepts_at_most_one_legal_keyword(self):
        sources = (
            "(start)a=b", "(end)a=b", "(once)a=b",
            "a=(start)b", "a=(end)b", "a=(return)b",
            "(once)a=(return)b", "(start)a=(end)b",
        )
        for source in sources:
            self.assertEqual(1, len(parse(source).exprs))

    def test_crlf_programs_are_accepted(self):
        program = parse("a=A\r\nb=B\r\n")
        self.assertEqual("AB", execute(program, "ab"))

    def test_error_reports_physical_line_number(self):
        with self.assertRaises(A2BParseException) as raised:
            parse("a=b\n\ninvalid")
        self.assertIn("L3", str(raised.exception))


class RepresentativeProgramTests(unittest.TestCase):
    def test_uppercase(self):
        program = parse(rules("a=A", "b=B", "c=C"))
        self.assertEqual("ABACBCAB", execute(program, "abacbcab"))

    def test_sort(self):
        program = parse(rules("ba=ab", "ca=ac", "cb=bc"))
        for value in ("a", "bab", "cacb", "bacbabaca", "ccaacbaaaa"):
            self.assertEqual("".join(sorted(value)), execute(program, value))

    def test_palindrome(self):
        program = parse(rules(
            "XaX=(return)false",
            "XbX=(return)false",
            "XcX=(return)false",
            "(end)aXa=",
            "(end)bXb=",
            "(end)cXc=",
            "(start)a=(end)Xa",
            "(start)b=(end)Xb",
            "(start)c=(end)Xc",
            "=(return)true",
        ))
        for value in ("", "a", "abcba", "abababa", "ccbbbcc", "abca"):
            expected = "true" if value == value[::-1] else "false"
            self.assertEqual(expected, execute(program, value))

    def test_reverse(self):
        program = parse(rules(
            "(once)=(end)XXXXXXXXXXXXXXXXXXXXXXX",
            "aX=(end)a",
            "bX=(end)b",
            "cX=(end)c",
            "X=",
        ))
        for value in ("a", "ab", "abcba", "cbccbc", "cccbabcccaaaaac"):
            self.assertEqual(value[::-1], execute(program, value))


class InterpreterLimitTests(unittest.TestCase):
    def test_operation_limit_stops_nonterminating_program(self):
        old_limit = A2B.EXECUTOR_OPERATION_LIMIT
        A2B.EXECUTOR_OPERATION_LIMIT = 3
        try:
            with self.assertRaises(A2BExecutionException) as raised:
                execute(parse("a=a"), "a")
            self.assertIn("Time Limit Exceeded", str(raised.exception))
        finally:
            A2B.EXECUTOR_OPERATION_LIMIT = old_limit

    def test_string_length_limit_checks_input_and_generated_state(self):
        old_limit = A2B.LINE_LENGTH_LIMIT
        A2B.LINE_LENGTH_LIMIT = 3
        try:
            with self.assertRaises(A2BExecutionException):
                execute(parse(""), "abcd")
            with self.assertRaises(A2BExecutionException):
                execute(parse("a=aaaa"), "a")
        finally:
            A2B.LINE_LENGTH_LIMIT = old_limit


if __name__ == "__main__":
    unittest.main()
