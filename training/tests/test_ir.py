import random
import unittest

from training.generation import GenerationConfig
from training.ir import (
    IROperation,
    TaskIR,
    apply_operation,
    compile_ir,
    describe_ir,
    generated_from_ir,
    verify_ir_oracle,
)


class IROracleTests(unittest.TestCase):
    def test_descriptions_follow_task_input_output_style(self):
        deletion = TaskIR(
            (IROperation("delete", {"symbols": ["a", "b"]}),),
            ("a", "b", "c"),
        )
        description = describe_ir(
            deletion,
            "table",
            minimum_input_length=0,
            maximum_input_length=7,
        )
        self.assertIn("输入：一个仅由 `a`、`b`、`c` 组成的字符串", description)
        self.assertIn("输出：删除所有 `a`、`b`", description)
        for vague in ("操作顺序", "依次删除", "小型文本机器", "公开样例"):
            self.assertNotIn(vague, description)

    def test_all_declared_operations_have_oracle_behavior(self):
        cases = (
            (IROperation("map", {"mapping": {"a": "b"}}), "aca", "bcb"),
            (IROperation("delete", {"symbols": ["a"]}), "abca", "bc"),
            (IROperation("replace_substring", {"old": "ab", "new": "x"}), "abab", "xx"),
            (IROperation("normalize_runs", {"symbols": ["a", "b"]}), "aaabb", "ab"),
            (IROperation("reverse", {}), "abc", "cba"),
            (IROperation("rotate", {"amount": 1, "direction": "left"}), "abc", "bca"),
            (IROperation("move_symbols", {"order": ["a", "b", "c"]}), "caba", "aabc"),
            (IROperation("recognize_pattern", {"pattern": "ab"}), "cab", "true"),
            (IROperation("unary_operation", {"operation": "increment", "symbol": "a"}), "aa", "aaa"),
            (IROperation("binary_operation", {"operation": "add", "separator": "+", "symbol": "a"}), "aa+a", "aaa"),
            (IROperation("encode", {"mapping": {"a": "x", "b": "y"}}), "aba", "xyx"),
            (IROperation("decode", {"mapping": {"x": "a", "y": "b"}}), "xyx", "aba"),
        )
        for operation, value, expected in cases:
            self.assertEqual(expected, apply_operation(operation, value), operation.kind)

        composed = IROperation(
            "compose",
            {
                "operations": [
                    IROperation("map", {"mapping": {"a": "b"}}),
                    IROperation("delete", {"symbols": ["c"]}),
                ]
            },
        )
        self.assertEqual("bb", apply_operation(composed, "aca"))

    def test_finite_state_oracle_supports_dfa_and_fst(self):
        base = {
            "states": ["q0", "q1"],
            "start_state": "q0",
            "transitions": {
                "q0\0a": "q1",
                "q0\0b": "q0",
                "q1\0a": "q0",
                "q1\0b": "q1",
            },
            "accepting_states": ["q1"],
        }
        dfa = IROperation("finite_state_transduction", dict(base, mode="dfa"))
        self.assertEqual("true", apply_operation(dfa, "ab"))
        outputs = {key: key[-1].upper() for key in base["transitions"]}
        fst = IROperation(
            "finite_state_transduction", dict(base, mode="fst", outputs=outputs)
        )
        self.assertEqual("ABA", apply_operation(fst, "aba"))


class IRCompilerTests(unittest.TestCase):
    def generated(self, operations, alphabet=("a", "b", "c")):
        ir = TaskIR(tuple(operations), tuple(alphabet))
        generated = generated_from_ir(
            ir,
            random.Random(4),
            GenerationConfig(max_program_lines=80, max_string_length=12),
            source_type="composed" if len(operations) > 1 else "enumerated",
            description_style="direct",
            max_input_length=3,
        )
        verify_ir_oracle(ir, generated, maximum_length=3)
        return generated

    def test_reliable_single_operation_compilers_match_oracle(self):
        operations = (
            IROperation("normalize_runs", {"symbols": ["a", "b", "c"]}),
            IROperation("reverse", {}),
            IROperation("rotate", {"amount": 1, "direction": "left"}),
            IROperation("move_symbols", {"order": ["a", "b", "c"]}),
            IROperation("recognize_pattern", {"pattern": "ab"}),
        )
        for operation in operations:
            self.generated((operation,))

    def test_depth_three_compiler_isolates_and_cleans_markers(self):
        operations = (
            IROperation("map", {"mapping": {"a": "b", "b": "a", "c": "c"}}),
            IROperation("delete", {"symbols": ["c"]}),
            IROperation("encode", {"mapping": {"a": "c", "b": "b"}}),
        )
        generated = self.generated(operations)
        self.assertEqual(3, generated.composition_depth)
        self.assertEqual(3, len(generated.parameters["marker_allocation"]))
        self.assertIn("marker_isolation", generated.concepts)


if __name__ == "__main__":
    unittest.main()
