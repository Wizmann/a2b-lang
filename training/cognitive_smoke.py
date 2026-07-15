"""从已审阅语义构建统一的认知多样性冒烟数据。"""

import hashlib
import importlib.util
import itertools
import json
import random
import shutil
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from A2B import parse

from .auxiliary import generate_auxiliary_tasks
from .baselines import run_baselines
from .dataset import (
    ExecutionOutcome,
    GeneratedProblem,
    QualityMetrics,
    behavior_signature,
    execute_with_limits,
    quality_metrics,
    select_public_hidden,
)
from .fingerprints import semantic_fingerprint, structural_fingerprint
from .generation import GeneratedProgram
from .jsonl import read_jsonl, write_jsonl
from .schema import validate_cognitive_task


RULES_VERSION = "1.0.0"
DEFAULT_SEED = 20260715
MAX_PROGRAM_LINES = 32
MAX_PROGRAM_CHARACTERS = 512
MAX_RUNTIME_STRING_LENGTH = 256

DOMAIN_BY_FAMILY = {
    "pointwise_transform": "string_rewrite",
    "run_structure": "string_rewrite",
    "boundary_transform": "string_rewrite",
    "bounded_occurrence_edit": "string_rewrite",
    "ordering_partition": "sequence_reordering",
    "segment_movement": "sequence_reordering",
    "reversal_symmetry_transform": "sequence_reordering",
    "positional_selection": "sequence_construction",
    "positional_expansion": "sequence_construction",
    "copy_and_reuse": "sequence_construction",
    "merge_and_deinterleave": "sequence_construction",
    "count_threshold": "counting_classification",
    "count_argextreme": "counting_classification",
    "modular_property": "counting_classification",
    "endpoint_relation": "relational_classification",
    "palindrome_and_pairing": "relational_classification",
    "conditional_transform": "relational_classification",
    "delimiter_field_logic": "delimited_fields",
    "representation_arithmetic": "numeric_representation",
    "carry_borrow_arithmetic": "numeric_representation",
}


@dataclass(frozen=True)
class Profile:
    family: str
    archetype: str
    scope: str
    memory: str
    traversal: str
    output: str
    invariant: str
    domain: str = "plain_string"
    depth: int = 1
    components: tuple = ()


def _p(family, archetype, scope, memory, traversal, output, invariant, **kwargs):
    return Profile(
        family, archetype, scope, memory, traversal, output, invariant, **kwargs
    )


TASK_PROFILES = {
    "1-1": _p("pointwise_transform", "replace_selected_symbol", "local", "none", "pointwise", "same_length", "each position is transformed independently"),
    "1-2": _p("pointwise_transform", "translate_complete_alphabet", "local", "none", "pointwise", "same_length", "one output symbol is emitted per input symbol"),
    "4-9": _p("pointwise_transform", "simultaneous_symbol_swap", "local", "marker_workspace", "left_to_right", "same_length", "simultaneous replacement must not cascade"),
    "1-3": _p("run_structure", "compress_all_runs", "local", "finite_state", "repeated_rewrite", "filtered", "one representative remains per maximal run"),
    "1-4": _p("run_structure", "delete_long_target_runs", "local", "finite_state", "repeated_rewrite", "filtered", "singleton target runs survive and longer runs disappear"),
    "3-1": _p("boundary_transform", "trim_target_both_ends", "boundary", "none", "bidirectional", "filtered", "only maximal boundary runs are removed"),
    "3-3": _p("boundary_transform", "replace_target_on_both_ends", "boundary", "marker_workspace", "bidirectional", "same_length", "interior target symbols remain unchanged"),
    "4-2": _p("bounded_occurrence_edit", "remove_first_k_matches", "global", "bounded_counter", "left_to_right", "filtered", "only the first k matching occurrences are removed"),
    "4-4": _p("bounded_occurrence_edit", "remove_last_k_matches", "global", "bounded_counter", "right_to_left", "filtered", "only the last k matching occurrences are removed"),
    "1-5": _p("ordering_partition", "total_alphabet_sort", "global", "none", "repeated_rewrite", "reordered", "all inversions under the declared order are eliminated"),
    "3-2": _p("segment_movement", "rotate_to_first_delimiter", "global", "marker_workspace", "left_to_right", "reordered", "the shortest prefix before the first delimiter moves to the end"),
    "3-4": _p("segment_movement", "swap_boundary_runs", "boundary", "marker_workspace", "bidirectional", "reordered", "the middle is preserved while boundary runs exchange places"),
    "4-7": _p("positional_selection", "drop_kth_position", "positional", "bounded_counter", "left_to_right", "filtered", "exactly one indexed position is removed"),
    "4-13": _p("positional_selection", "select_middle_symbol", "positional", "marker_workspace", "bidirectional", "scalar", "equal numbers of symbols are discarded from both ends"),
    "4-15": _p("positional_expansion", "repeat_by_one_based_index", "positional", "bounded_counter", "left_to_right", "expanded", "position i contributes exactly i copies"),
    "4-5": _p("reversal_symmetry_transform", "swap_endpoints", "boundary", "marker_workspace", "bidirectional", "reordered", "the interior is fixed while endpoints exchange"),
    "4-6": _p("reversal_symmetry_transform", "reverse_whole_string", "global", "marker_workspace", "right_to_left", "reordered", "output position i equals the symmetric input position"),
    "2-2": _p("count_threshold", "at_least_k_occurrences", "global", "bounded_counter", "repeated_rewrite", "boolean", "the target count is compared with a lower bound"),
    "2-3": _p("count_threshold", "exact_total_length", "global", "bounded_counter", "repeated_rewrite", "boolean", "all symbols contribute to one exact length count"),
    "1-6": _p("count_argextreme", "majority_of_two_symbols", "global", "symbol_counter", "repeated_rewrite", "scalar", "pair cancellation leaves the unique majority"),
    "2-8": _p("count_argextreme", "return_unique_most_frequent", "global", "symbol_counter", "repeated_rewrite", "scalar", "the unique maximum frequency determines the output symbol"),
    "3-6": _p("count_argextreme", "keep_unique_most_frequent", "global", "symbol_counter", "repeated_rewrite", "filtered", "count comparison selects which occurrences survive"),
    "2-4": _p("modular_property", "length_remainder", "global", "parity_state", "repeated_rewrite", "scalar", "only the length residue is retained"),
    "2-5": _p("modular_property", "all_symbol_counts_odd_or_zero", "global", "parity_state", "repeated_rewrite", "boolean", "one parity bit is maintained for each symbol"),
    "4-10": _p("modular_property", "select_positions_by_parity", "positional", "parity_state", "left_to_right", "filtered", "selection depends on the index modulo two"),
    "3-5": _p("endpoint_relation", "endpoints_equal", "boundary", "finite_state", "bidirectional", "boolean", "the first and last symbols are compared"),
    "3-7": _p("palindrome_and_pairing", "palindrome", "global", "marker_workspace", "bidirectional", "boolean", "symmetric pairs must match until the center"),
    "4-12": _p("conditional_transform", "contains_symbol_choose_mapping", "global", "finite_state", "left_to_right", "same_length", "a global predicate selects one of two mappings"),
    "4-8": _p("copy_and_reuse", "append_fixed_length_prefix_copy", "global", "marker_workspace", "left_to_right", "expanded", "a selected prefix is preserved and emitted again"),
    "4-11": _p("copy_and_reuse", "duplicate_whole_input", "global", "marker_workspace", "left_to_right", "expanded", "the complete input is stored and emitted twice"),
    "4-16": _p("merge_and_deinterleave", "interleave_equal_fields", "multi_field", "marker_workspace", "left_to_right", "reordered", "corresponding positions alternate between fields"),
    "5-1": _p("representation_arithmetic", "binary_to_unary", "global", "marker_workspace", "left_to_right", "expanded", "the represented numeric value is invariant across encodings", domain="binary_number"),
    "5-2": _p("carry_borrow_arithmetic", "binary_increment", "global", "carry_borrow", "right_to_left", "expanded", "carry propagates through the trailing one bits", domain="binary_number"),
    "5-3": _p("carry_borrow_arithmetic", "binary_addition", "multi_field", "carry_borrow", "right_to_left", "expanded", "column sums preserve numeric addition with carry", domain="binary_number"),
    "5-4": _p("carry_borrow_arithmetic", "binary_subtraction", "multi_field", "carry_borrow", "right_to_left", "filtered", "borrow propagation preserves numeric subtraction", domain="binary_number"),
}


@dataclass(frozen=True)
class ExtraSpec:
    id: str
    profile: Profile
    description: str
    program: str
    oracle_name: str
    input_kind: str = "string"
    source_type: str = "template"


def _extra(id_, profile, description, program, oracle, **kwargs):
    return ExtraSpec(id_, profile, description, program.strip(), oracle, **kwargs)


EXTRAS = (
    _extra("replace_first_then_sort", _p("bounded_occurrence_edit", "replace_first_then_sort", "global", "bounded_counter", "repeated_rewrite", "reordered", "the bounded edit changes the multiset consumed by sorting", depth=2, components=("replace_first_a", "sort")), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：只将最左侧的一个 `a` 替换为 `b`，再按 `a < b < c` 排序。", "(once)a=b\nba=ab\nca=ac\ncb=bc", "replace_first_sort", source_type="composed"),
    _extra("stable_partition_b", _p("ordering_partition", "stable_binary_partition", "global", "none", "repeated_rewrite", "reordered", "non-target symbols keep relative order while targets move last"), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：稳定地将所有 `b` 移到末尾，`a` 和 `c` 的相对顺序保持不变。", "ba=ab\nbc=cb", "stable_partition"),
    _extra("sorted_unique", _p("ordering_partition", "sort_then_deduplicate", "global", "none", "repeated_rewrite", "filtered", "the output is sorted and contains each observed symbol once", depth=2, components=("sort", "deduplicate")), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：按 `a < b < c` 排序后，每种出现过的字符只保留一个。", "ba=ab\nca=ac\ncb=bc\naa=a\nbb=b\ncc=c", "sorted_unique", source_type="composed"),
    _extra("compress_then_reverse", _p("run_structure", "compress_then_reverse", "global", "marker_workspace", "bidirectional", "reordered", "run compression changes the sequence consumed by reversal", depth=2, components=("compress_runs", "reverse")), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：将每段连续相同字符压缩为一个字符，再反转字符串。", "aa=a\nbb=b\ncc=c\n(once)=(end)FFFFFFFF\naF=(end)a\nbF=(end)b\ncF=(end)c\nF=", "compress_reverse", source_type="composed"),
    _extra("trim_then_duplicate", _p("boundary_transform", "trim_then_duplicate", "boundary", "marker_workspace", "left_to_right", "expanded", "boundary trimming changes the string consumed by duplication", depth=2, components=("trim_boundary_a", "duplicate_each")), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：删除两端所有连续的 `a`，再将剩余的每个字符输出两次。", "(start)a=\n(end)a=\n(once)=(start)X\nXa=aaX\nXb=bbX\nXc=ccX\n(end)X=", "trim_duplicate", source_type="composed"),
    _extra("rotate_then_swap_symbols", _p("segment_movement", "rotate_then_symbol_swap", "global", "marker_workspace", "left_to_right", "reordered", "rotation changes positions before a simultaneous symbol swap", depth=2, components=("rotate_left_one", "swap_a_b")), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：循环左移一位后，同时交换 `a` 和 `b`，`c` 保持不变。", "(once)=(start)X\nXa=(end)a\nXb=(end)b\nXc=(end)c\nX=\n(once)=(start)Y\nYa=bY\nYb=aY\nYc=cY\n(end)Y=", "rotate_swap", source_type="composed"),
    _extra("duplicate_then_delete_b", _p("positional_expansion", "duplicate_then_filter", "positional", "marker_workspace", "left_to_right", "expanded", "expansion occurs before filtering the selected symbol", depth=2, components=("duplicate_each", "delete_b")), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：将每个字符连续输出两次，然后删除所有 `b`。", "(once)=(start)X\nXa=aaX\nXb=bbX\nXc=ccX\n(end)X=\nb=", "duplicate_delete_b", source_type="composed"),
    _extra("duplicate_odd_positions", _p("positional_expansion", "duplicate_odd_positions", "positional", "parity_state", "left_to_right", "expanded", "odd positions contribute twice and even positions once"), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：奇数位置的字符输出两次，偶数位置的字符输出一次。", "(once)=(start)XX\nXXa=aaX\nXXb=bbX\nXXc=ccX\nXa=aXX\nXb=bXX\nXc=cXX\nX=", "duplicate_odd"),
    _extra("drop_three_then_normalize", _p("positional_selection", "drop_prefix_then_normalize_runs", "positional", "bounded_counter", "left_to_right", "filtered", "prefix deletion changes the runs consumed by normalization", depth=2, components=("drop_first_three", "normalize_runs")), "输入：一个仅由 `a`、`b`、`c` 组成且长度至少为 3 的字符串，长度不超过 8。\n输出：删除前三个字符，再压缩剩余字符串中的连续相同字符。", "(once)=(start)X\nXa=Y\nXb=Y\nXc=Y\nYa=Z\nYb=Z\nYc=Z\nZa=\nZb=\nZc=\naa=a\nbb=b\ncc=c", "drop_three_normalize", input_kind="min_three", source_type="composed"),
    _extra("filtered_length_at_most_three", _p("count_threshold", "filtered_length_at_most_k", "global", "bounded_counter", "repeated_rewrite", "boolean", "filtering changes the length consumed by the threshold", depth=2, components=("delete_c", "length_at_most_three")), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：删除所有 `c` 后，剩余长度不超过 3 时输出 `true`，否则输出 `false`。", "c=\nb=a\naaaa=(return)false\n=(return)true", "filtered_length_le_three", source_type="composed"),
    _extra("first_symbol", _p("endpoint_relation", "return_first_symbol", "boundary", "finite_state", "left_to_right", "scalar", "the left endpoint alone determines the output"), "输入：一个由 `a`、`b`、`c` 组成的非空字符串，长度不超过 8。\n输出：字符串的第一个字符。", "(start)a=(return)a\n(start)b=(return)b\n(start)c=(return)c", "first", input_kind="nonempty"),
    _extra("last_symbol", _p("endpoint_relation", "return_last_symbol", "boundary", "finite_state", "right_to_left", "scalar", "the right endpoint alone determines the output"), "输入：一个由 `a`、`b`、`c` 组成的非空字符串，长度不超过 8。\n输出：字符串的最后一个字符。", "(end)a=(return)a\n(end)b=(return)b\n(end)c=(return)c", "last", input_kind="nonempty"),
    _extra("non_palindrome", _p("palindrome_and_pairing", "non_palindrome", "global", "marker_workspace", "bidirectional", "boolean", "a mismatched symmetric pair makes the predicate true"), "输入：一个仅由 `a`、`b`、`c` 组成的非空字符串，长度不超过 8。\n输出：不是回文串时输出 `true`，否则输出 `false`。", "(end)aXaX=\n(end)bXbX=\n(end)cXcX=\n(start)a=(end)XaX\n(start)b=(end)XbX\n(start)c=(end)XcX\nXX=(return)true\n=(return)false", "non_palindrome", input_kind="nonempty"),
    _extra("palindrome_ignoring_c", _p("palindrome_and_pairing", "palindrome_after_filter", "global", "marker_workspace", "bidirectional", "boolean", "filtering changes which symbols become symmetric pairs", depth=2, components=("filter_c", "palindrome")), "输入：一个仅由 `a`、`b`、`c` 组成的非空字符串，长度不超过 8。\n输出：删除所有 `c` 后是回文串时输出 `true`，否则输出 `false`。", "c=\n(end)aXaX=\n(end)bXbX=\n(start)a=(end)XaX\n(start)b=(end)XbX\nXX=(return)false\n=(return)true", "palindrome_ignoring_c", input_kind="nonempty", source_type="composed"),
    _extra("filter_then_reverse", _p("reversal_symmetry_transform", "filter_then_reverse", "global", "marker_workspace", "right_to_left", "filtered", "filtering changes the sequence consumed by reversal", depth=2, components=("delete_c", "reverse")), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：删除所有 `c`，再反转剩余字符串。", "c=\n(once)=(end)FFFFFFFF\naF=(end)a\nbF=(end)b\nF=", "filter_reverse", source_type="composed"),
    _extra("contains_b_delete_a", _p("conditional_transform", "contains_symbol_choose_delete_or_identity", "global", "finite_state", "left_to_right", "filtered", "the presence predicate decides whether target symbols are removed"), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：如果输入包含 `b`，删除所有 `a`；否则保持原字符串不变。", "(once)b=bX\n(once)=Y\nX=(start)Y\nYYa=YY\nYb=bY\nYc=cY\nYa=aY\nY=", "conditional_delete"),
    _extra("odd_length_map_a", _p("conditional_transform", "length_parity_choose_mapping", "global", "parity_state", "left_to_right", "same_length", "length parity selects whether a mapping is applied"), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：长度为奇数时将所有 `a` 替换为 `b`；长度为偶数时保持不变。", "(once)=(start)X\nXa=aY\nXb=bY\nXc=cY\nYa=aX\nYb=bX\nYc=cX\n(end)X=\n(end)Y=(start)Z\nZa=bZ\nZb=bZ\nZc=cZ\n(end)Z=", "conditional_odd_map"),
    _extra("select_left_field", _p("delimiter_field_logic", "select_left_field", "multi_field", "none", "right_to_left", "filtered", "the delimiter separates the retained field from the discarded field", domain="delimited_fields"), "输入：两个非空一元字符串，以逗号分隔，例如 `aaa,aa`。\n输出：逗号左侧的字符串。", ",a=,\n,=", "select_left", input_kind="fields"),
    _extra("select_right_field", _p("delimiter_field_logic", "select_right_field", "multi_field", "none", "left_to_right", "filtered", "the delimiter separates the discarded field from the retained field", domain="delimited_fields"), "输入：两个非空一元字符串，以逗号分隔，例如 `aaa,aa`。\n输出：逗号右侧的字符串。", "a,=,\n,=", "select_right", input_kind="fields"),
    _extra("compare_unary_fields", _p("delimiter_field_logic", "compare_field_lengths", "multi_field", "symbol_counter", "repeated_rewrite", "scalar", "pair cancellation reveals the longer field", domain="delimited_fields"), "输入：两个非空一元字符串，以逗号分隔。\n输出：左侧较长时输出 `left`，右侧较长时输出 `right`，长度相等时输出 `equal`。", "a,a=,\na,=(return)left\n,a=(return)right\n,=(return)equal", "compare_fields", input_kind="fields"),
    _extra("append_first_symbol", _p("copy_and_reuse", "append_first_symbol_copy", "global", "marker_workspace", "left_to_right", "expanded", "the first symbol is remembered until the end"), "输入：一个由 `a`、`b`、`c` 组成的非空字符串，长度不超过 8。\n输出：在原字符串末尾再添加一次首字符。", "(once)=(start)X\nXa=aA\nXb=bB\nXc=cC\nAa=aA\nAb=bA\nAc=cA\nBa=aB\nBb=bB\nBc=cB\nCa=aC\nCb=bC\nCc=cC\n(end)A=a\n(end)B=b\n(end)C=c", "append_first", input_kind="nonempty"),
    _extra("deinterleave", _p("merge_and_deinterleave", "split_odd_even_positions", "global", "marker_workspace", "left_to_right", "multi_field", "odd and even positions preserve their internal order", domain="delimited_fields"), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：先输出奇数位置字符，再输出逗号，再输出偶数位置字符；两部分保持原顺序。", "(once)=(start)X\nXa=AY\nXb=BY\nXc=CY\nYa=DX\nYb=EX\nYc=FX\n(end)X=,\n(end)Y=,\nDA=AD\nDB=BD\nDC=CD\nEA=AE\nEB=BE\nEC=CE\nFA=AF\nFB=BF\nFC=CF\nD,=,D\nE,=,E\nF,=,F\nA=a\nB=b\nC=c\nD=a\nE=b\nF=c", "deinterleave"),
    _extra("swap_adjacent_pairs", _p("merge_and_deinterleave", "swap_adjacent_pairs", "positional", "marker_workspace", "left_to_right", "reordered", "each complete adjacent pair is reversed independently"), "输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。\n输出：交换第 1、2 个字符，交换第 3、4 个字符，以此类推；末尾未配对字符保持不变。", "(once)=(start)X\nXa=A\nXb=B\nXc=C\nAa=aaX\nAb=baX\nAc=caX\nBa=abX\nBb=bbX\nBc=cbX\nCa=acX\nCb=bcX\nCc=ccX\n(end)A=a\n(end)B=b\n(end)C=c\n(end)X=", "swap_pairs"),
    _extra("unary_increment", _p("representation_arithmetic", "unary_increment", "global", "none", "left_to_right", "expanded", "one output symbol is added to the represented value", domain="unary_number"), "输入：一个仅由 `a` 组成的字符串，可以为空，长度不超过 16。\n输出：在末尾添加一个 `a`。", "(once)=(end)a", "unary_increment", input_kind="unary", source_type="enumerated"),
    _extra("unary_double", _p("representation_arithmetic", "unary_double", "global", "marker_workspace", "left_to_right", "expanded", "the unary output length is twice the input length", domain="unary_number"), "输入：一个仅由 `a` 组成的字符串，可以为空，长度不超过 12。\n输出：长度加倍的一元字符串。", "(once)=(start)X\nXa=aaX\n(end)X=", "unary_double", input_kind="unary", source_type="enumerated"),
)


def _sha(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _oracle(name, value):
    if name == "replace_first":
        return value.replace("a", "b", 1)
    if name == "replace_first_sort":
        return "".join(sorted(value.replace("a", "b", 1)))
    if name == "stable_partition":
        return "".join(char for char in value if char != "b") + "b" * value.count("b")
    if name == "sorted_unique":
        return "".join(char for char in "abc" if char in value)
    if name == "compress_reverse":
        compressed = "".join(
            char
            for index, char in enumerate(value)
            if index == 0 or char != value[index - 1]
        )
        return compressed[::-1]
    if name == "trim_duplicate":
        return "".join(char * 2 for char in value.strip("a"))
    if name == "rotate_left":
        return value[1:] + value[:1]
    if name == "rotate_swap":
        return (value[1:] + value[:1]).translate(str.maketrans("ab", "ba"))
    if name == "duplicate_each":
        return "".join(char * 2 for char in value)
    if name == "duplicate_delete_b":
        return "".join(char * 2 for char in value if char != "b")
    if name == "duplicate_odd":
        return "".join(char * (2 if index % 2 == 0 else 1) for index, char in enumerate(value))
    if name == "length_le_three":
        return "true" if len(value) <= 3 else "false"
    if name == "filtered_length_le_three":
        return "true" if len(value.replace("c", "")) <= 3 else "false"
    if name == "drop_three_normalize":
        remainder = value[3:]
        return "".join(
            char
            for index, char in enumerate(remainder)
            if index == 0 or char != remainder[index - 1]
        )
    if name == "first":
        return value[0]
    if name == "last":
        return value[-1]
    if name == "non_palindrome":
        return "true" if value != value[::-1] else "false"
    if name == "palindrome_ignoring_c":
        filtered = value.replace("c", "")
        return "true" if filtered == filtered[::-1] else "false"
    if name == "filter_reverse":
        return value.replace("c", "")[::-1]
    if name == "conditional_delete":
        return value.replace("a", "") if "b" in value else value
    if name == "conditional_odd_map":
        return value.replace("a", "b") if len(value) % 2 else value
    if name == "select_left":
        return value.split(",", 1)[0]
    if name == "select_right":
        return value.split(",", 1)[1]
    if name == "compare_fields":
        left, right = value.split(",", 1)
        return "left" if len(left) > len(right) else "right" if len(right) > len(left) else "equal"
    if name == "append_first":
        return value + value[0]
    if name == "deinterleave":
        return value[::2] + "," + value[1::2]
    if name == "swap_pairs":
        chars = list(value)
        for index in range(0, len(chars) - 1, 2):
            chars[index], chars[index + 1] = chars[index + 1], chars[index]
        return "".join(chars)
    if name == "unary_increment":
        return value + "a"
    if name == "unary_double":
        return value * 2
    raise KeyError(name)


def _normalize_runs(value):
    return "".join(
        char
        for index, char in enumerate(value)
        if index == 0 or char != value[index - 1]
    )


def _composition_counterfactuals(name, value):
    """Return component-deletion and swapped-order oracle outputs."""
    if name == "replace_first_sort":
        return ("".join(sorted(value)), value.replace("a", "b", 1)), "".join(sorted(value)).replace("a", "b", 1)
    if name == "sorted_unique":
        return (_normalize_runs(value), "".join(sorted(value))), "".join(sorted(_normalize_runs(value)))
    if name == "compress_reverse":
        return (value[::-1], _normalize_runs(value)), _normalize_runs(value[::-1])
    if name == "trim_duplicate":
        return ("".join(char * 2 for char in value), value.strip("a")), ("".join(char * 2 for char in value)).strip("a")
    if name == "rotate_swap":
        swapped = value.translate(str.maketrans("ab", "ba"))
        return (swapped, value[1:] + value[:1]), swapped[1:] + swapped[:1]
    if name == "duplicate_delete_b":
        return (value.replace("b", ""), "".join(char * 2 for char in value)), "".join(char * 2 for char in value.replace("b", ""))
    if name == "drop_three_normalize":
        return (_normalize_runs(value), value[3:]), _normalize_runs(value)[3:]
    if name == "filtered_length_le_three":
        threshold = "true" if len(value) <= 3 else "false"
        return (threshold, value.replace("c", "")), threshold
    if name == "filter_reverse":
        return (value[::-1], value.replace("c", "")), value[::-1].replace("c", "")
    if name == "palindrome_ignoring_c":
        palindrome = "true" if value == value[::-1] else "false"
        return (palindrome, value.replace("c", "")), palindrome
    raise KeyError(name)


def _extra_inputs(spec, rng):
    if spec.input_kind == "fields":
        return tuple("a" * left + "," + "a" * right for left in range(1, 13) for right in range(1, 13))
    if spec.input_kind == "unary":
        return tuple("a" * length for length in range(17))
    minimum = 3 if spec.input_kind == "min_three" else 1 if spec.input_kind == "nonempty" else 0
    values = ["".join(chars) for length in range(minimum, 5) for chars in itertools.product("abc", repeat=length)]
    seen = set(values)
    while len(values) < 180:
        length = rng.randint(max(5, minimum), 8)
        value = "".join(rng.choice("abc") for _ in range(length))
        if value not in seen:
            seen.add(value)
            values.append(value)
    return tuple(values)


def _features(program):
    return tuple(name for name in ("once", "start", "end", "return") if "(%s)" % name in program) or ("plain_rewrite",)


def _description_from_task(record):
    constraints = record.get("constraints", {})
    limits = []
    if "min_length" in constraints and "max_length" in constraints:
        limits.append("长度为 %s 到 %s" % (constraints["min_length"], constraints["max_length"]))
    if constraints.get("equal_lengths"):
        limits.append("两个字段长度相同")
    suffix = "\n限制：" + "；".join(limits) + "。" if limits else ""
    return "输入：%s\n输出：%s%s" % (record["input"], record["output"], suffix)


def _load_groundtruth(path):
    spec = importlib.util.spec_from_file_location("curated_groundtruth_" + path.parent.name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.solve


def _generated(profile, *, program, description, template, source_type, parameters):
    if len(program.splitlines()) > MAX_PROGRAM_LINES or len(program) > MAX_PROGRAM_CHARACTERS:
        raise ValueError("program limit exceeded for %s" % template)
    features = _features(program)
    return GeneratedProgram(
        program=program,
        template_family=template,
        template_version=RULES_VERSION,
        generator_name="cognitive_catalog",
        generator_version=RULES_VERSION,
        difficulty=min(5, 1 + len(program.splitlines()) // 6 + (profile.depth - 1)),
        allowed_features=features,
        parameters={
            **parameters,
            "cognitive_family": profile.family,
            "semantic_archetype": profile.archetype,
            "semantic_components": list(profile.components),
        },
        description=description,
        tags=("dataset_smoke", "cognitive_review"),
        limits={
            "max_program_lines": MAX_PROGRAM_LINES,
            "max_program_characters": MAX_PROGRAM_CHARACTERS,
            "max_string_length": MAX_RUNTIME_STRING_LENGTH,
        },
        concepts=tuple(dict.fromkeys((profile.family,) + profile.components)),
        task_domain=DOMAIN_BY_FAMILY[profile.family],
        algorithm_family=profile.family,
        composition_depth=profile.depth,
        required_features=features,
        description_style="direct",
        source_type=source_type,
    )


def _problem(generated, profile, outcomes, rng, public=None, hidden=None):
    outcomes = tuple(outcomes)
    if public is None:
        public, hidden = select_public_hidden(rng, outcomes, 10, min(48, len(outcomes) - 10))
    metrics = quality_metrics(generated, outcomes, public, hidden)
    signature = behavior_signature(outcomes)
    alphabet = generated.parameters.get("input_alphabet", ())
    semantic = semantic_fingerprint(outcomes, alphabet)
    structural = structural_fingerprint(generated.program, alphabet)
    identifier = "cognitive_%s-%s" % (profile.archetype, signature[:12])
    lengths = [len(item.input) for item in outcomes]
    cognitive_payload = {
        "family": profile.family,
        "archetype": profile.archetype,
        "scope": profile.scope,
        "memory": profile.memory,
        "traversal": profile.traversal,
        "output": profile.output,
        "invariant": profile.invariant,
    }
    components = list(range(profile.depth))
    hardening = {
        "declared_composition_depth": profile.depth,
        "effective_composition_depth": profile.depth,
        "effective_components": components,
        "dead_components": [],
        "component_interaction": "semantic_dependency" if profile.depth > 1 else "not_composed",
        "order_sensitive": False,
        "order_distinguishing_input": None,
        "order_comparison": None,
        "order_outputs": None,
        "reducible_to_single_stage": False,
        "normalized_semantic_ir": {"cognitive": cognitive_payload, "components": list(profile.components)},
        "genuine_composition": profile.depth > 1,
        "superficial_composition": False,
        "specification_level": "functional",
        "solution_revealing_score": 0.15,
        "concrete_behavior_fingerprint": signature,
        "alpha_normalized_behavior_fingerprint": semantic,
        "semantic_ir_fingerprint": _sha(cognitive_payload),
        "ontology_errors": [],
        "root_problem_id": identifier,
        "program_lineage_id": "program:" + signature,
        "mutant_family_id": "mutant:" + identifier,
        "alpha_equivalence_class": structural,
        "construction_domain": {"min_length": min(lengths), "max_length": max(min(lengths), min(3, max(lengths)))},
        "public_domain": {"min_length": min(len(case["input"]) for case in public), "max_length": max(len(case["input"]) for case in public)},
        "hidden_domain": {"min_length": min(len(case["input"]) for case in hidden), "max_length": max(len(case["input"]) for case in hidden)},
        "generalization_domain": {"min_length": min(lengths), "max_length": max(lengths)},
        "audit_domain": {"min_length": min(lengths), "max_length": max(lengths), "probe_cap": len(outcomes)},
        "audit_reference_verification": {"attempted": len(outcomes), "verified": len(outcomes), "fraction": 1.0},
        "cognitive_family": profile.family,
        "semantic_archetype": profile.archetype,
        "parameter_instance": {},
        "information_scope": profile.scope,
        "memory_model": profile.memory,
        "traversal_model": profile.traversal,
        "output_shape": profile.output,
        "primary_invariant": profile.invariant,
        "cognitive_signature": _sha(cognitive_payload),
    }
    return GeneratedProblem(identifier, generated, tuple(public), tuple(hidden), signature, semantic, structural, metrics, hardening)


def _load_task_problem(root, task_id, profile, rng):
    directory = root / "tasks" / task_id
    task = next(read_jsonl(directory / "task.jsonl"))
    program = (directory / "solution.a2b").read_text(encoding="utf-8").strip()
    solve = _load_groundtruth(directory / "groundtruth.py")
    pretests = list(read_jsonl(directory / "testcase_pretest.jsonl"))
    full = list(read_jsonl(directory / "testcase_full.jsonl"))
    cases = []
    seen = set()
    parsed = parse(program)
    for case in pretests + full:
        if case["input"] in seen:
            continue
        seen.add(case["input"])
        expected = solve(case["input"])
        if expected != case["output"]:
            raise ValueError("groundtruth mismatch for task %s" % task_id)
        outcome = execute_with_limits(parsed, case["input"], max_steps=100000, max_length=MAX_RUNTIME_STRING_LENGTH)
        if not outcome.terminating or outcome.output != expected:
            raise ValueError("A=B mismatch for task %s on %r" % (task_id, case["input"]))
        cases.append(outcome)
    public_inputs = {case["input"] for case in pretests}
    hidden = tuple(case for case in full if case["input"] not in public_inputs)
    constraints = task.get("constraints", {})
    alphabet = list(constraints.get("alphabet", ["a", "b", "c"]))
    for separator in (constraints.get("separator"), "+", "-"):
        if separator and separator in "".join(case["input"] for case in pretests) and separator not in alphabet:
            alphabet.append(separator)
    generated = _generated(
        profile,
        program=program,
        description=_description_from_task(task),
        template="curated_task_" + task_id,
        source_type="handwritten",
        parameters={
            "source_task_id": task_id,
            "input_alphabet": alphabet,
            "min_input_length": min(len(item.input) for item in cases),
            "max_input_length": max(len(item.input) for item in cases),
        },
    )
    return _problem(generated, profile, cases, rng, tuple(pretests), hidden)


def _extra_problem(spec, rng):
    inputs = _extra_inputs(spec, rng)
    parsed = parse(spec.program)
    outcomes = []
    component_effective = [False] * spec.profile.depth
    order_sensitive = False
    distinguishing_input = None
    order_outputs = None
    for value in inputs:
        expected = _oracle(spec.oracle_name, value)
        outcome = execute_with_limits(parsed, value, max_steps=100000, max_length=MAX_RUNTIME_STRING_LENGTH)
        if not outcome.terminating or outcome.output != expected:
            raise ValueError("extra %s mismatch on %r: %r != %r" % (spec.id, value, outcome.output, expected))
        outcomes.append(outcome)
        if spec.profile.depth > 1:
            ablated, swapped = _composition_counterfactuals(
                spec.oracle_name,
                value,
            )
            for index, output in enumerate(ablated):
                component_effective[index] |= output != expected
            if not order_sensitive and swapped != expected:
                order_sensitive = True
                distinguishing_input = value
                order_outputs = {"declared": expected, "comparison": swapped}
    alphabet = sorted(set("".join(inputs)))
    generated = _generated(
        spec.profile,
        program=spec.program,
        description=spec.description,
        template="curated_extra_" + spec.id,
        source_type=spec.source_type,
        parameters={
            "input_alphabet": alphabet,
            "min_input_length": min(map(len, inputs)),
            "max_input_length": max(map(len, inputs)),
            "oracle_name": spec.oracle_name,
        },
    )
    problem = _problem(generated, spec.profile, outcomes, rng)
    if spec.profile.depth > 1:
        if not all(component_effective):
            raise ValueError(
                "composition %s contains an ineffective component" % spec.id
            )
        hardening = dict(problem.hardening)
        hardening.update(
            {
                "component_interaction": (
                    "genuine_order_sensitive"
                    if order_sensitive
                    else "genuine_commuting"
                ),
                "order_sensitive": order_sensitive,
                "order_distinguishing_input": distinguishing_input,
                "order_comparison": list(reversed(spec.profile.components)),
                "order_outputs": order_outputs,
                "composition_component_probe": {
                    "audit_input_count": len(inputs),
                    "component_effective": component_effective,
                    "all_components_effective": all(component_effective),
                    "swapped_order_checked": True,
                },
            }
        )
        problem = replace(problem, hardening=hardening)
    return problem


def generate_cognitive_smoke(root, *, seed=DEFAULT_SEED):
    root = Path(root)
    rng = random.Random(seed)
    problems = [_load_task_problem(root, task_id, profile, rng) for task_id, profile in sorted(TASK_PROFILES.items())]
    problems.extend(_extra_problem(spec, rng) for spec in EXTRAS)
    if len(problems) != 60:
        raise AssertionError("cognitive catalog must contain exactly 60 archetypes")
    signatures = [problem.behavior_signature for problem in problems]
    if len(signatures) != len(set(signatures)):
        raise ValueError("cognitive catalog contains duplicate concrete behavior")
    return tuple(sorted(problems, key=lambda problem: (problem.generated_program.algorithm_family, problem.id)))


def split_cognitive(problems, *, seed=DEFAULT_SEED):
    by_family = {}
    for problem in problems:
        by_family.setdefault(problem.generated_program.algorithm_family, []).append(problem)
    splits = {"train": [], "validation": [], "test": []}
    for family, values in sorted(by_family.items()):
        values = sorted(values, key=lambda item: _sha([seed, item.id]))
        if len(values) != 3:
            raise ValueError("family %s must contain exactly three archetypes" % family)
        splits["train"].extend(values[:2])
        target = "validation" if int(_sha([seed, family])[:2], 16) % 2 else "test"
        splits[target].append(values[2])
    # Keep validation/test exactly balanced while preserving two train roots per family.
    while len(splits["validation"]) > 10:
        splits["test"].append(splits["validation"].pop())
    while len(splits["test"]) > 10:
        splits["validation"].append(splits["test"].pop())
    return {name: tuple(sorted(values, key=lambda item: item.id)) for name, values in splits.items()}


def cognitive_statistics(problems, splits, auxiliary):
    family = Counter(p.hardening["cognitive_family"] for p in problems)
    archetypes = Counter(p.hardening["semantic_archetype"] for p in problems)
    sources = Counter(p.generated_program.source_type for p in problems)
    domains = Counter(p.generated_program.task_domain for p in problems)
    depths = Counter(p.generated_program.composition_depth for p in problems)
    alpha = Counter(p.hardening["alpha_equivalence_class"] for p in problems)
    compositions = [
        problem
        for problem in problems
        if problem.generated_program.composition_depth > 1
    ]
    all_steps = [
        step
        for problem in problems
        for step in problem.quality.execution_steps
    ]
    baseline_by_split = {
        name: [asdict(result) for result in run_baselines(values)]
        for name, values in splits.items()
    }
    return {
        "synthesis_problem_count": len(problems),
        "cognitive_family_count": len(family),
        "semantic_archetype_count": len(archetypes),
        "cognitive_family_distribution": dict(sorted(family.items())),
        "semantic_archetype_distribution": dict(sorted(archetypes.items())),
        "source_type_distribution": dict(sorted(sources.items())),
        "task_domain_distribution": dict(sorted(domains.items())),
        "composition_depth_distribution": {str(k): v for k, v in sorted(depths.items())},
        "genuine_composition_count": sum(p.hardening["genuine_composition"] for p in problems),
        "genuine_composition_fraction": len(compositions) / len(problems),
        "composition_component_probe_failures": sum(
            not problem.hardening.get("composition_component_probe", {}).get(
                "all_components_effective",
                False,
            )
            for problem in compositions
        ),
        "operational_description_count": sum(p.hardening["specification_level"] == "operational" for p in problems),
        "behavior_duplicates": len(problems) - len({p.behavior_signature for p in problems}),
        "alpha_equivalent_problem_count": sum(count for count in alpha.values() if count > 1),
        "max_alpha_cluster_size": max(alpha.values()),
        "reference_verification_fraction": sum(p.hardening["audit_reference_verification"]["fraction"] == 1 for p in problems) / len(problems),
        "program_line_distribution": dict(sorted(Counter(len(p.generated_program.program.splitlines()) for p in problems).items())),
        "execution_steps": {
            "minimum": min(all_steps),
            "maximum": max(all_steps),
            "mean": sum(all_steps) / len(all_steps),
        },
        "identity_fraction_mean": sum(p.quality.identity_fraction for p in problems) / len(problems),
        "constant_fraction_mean": sum(p.quality.constant_fraction for p in problems) / len(problems),
        "terminating_fraction": sum(p.quality.terminating_fraction == 1 for p in problems) / len(problems),
        "public_hidden_overlap": sum(p.quality.public_hidden_overlap for p in problems),
        "baseline_by_split": baseline_by_split,
        "split_sizes": {name: len(values) for name, values in splits.items()},
        "auxiliary_counts": {name: len(values) for name, values in auxiliary.items()},
    }


def cognitive_checks(statistics):
    family_values = statistics["cognitive_family_distribution"].values()
    checks = {
        "synthesis_archetypes_60": statistics["synthesis_problem_count"] == 60 and statistics["semantic_archetype_count"] == 60,
        "cognitive_families_20": statistics["cognitive_family_count"] == 20,
        "three_archetypes_per_family": set(family_values) == {3},
        "reference_verification_100_percent": statistics["reference_verification_fraction"] == 1.0,
        "behavior_duplicates_zero": statistics["behavior_duplicates"] == 0,
        "alpha_equivalent_fraction_zero": statistics["alpha_equivalent_problem_count"] == 0,
        "operational_descriptions_zero": statistics["operational_description_count"] == 0,
        "genuine_composition_fraction_15_to_25_percent": 0.15 <= statistics["genuine_composition_fraction"] <= 0.25,
        "composition_components_all_effective": statistics["composition_component_probe_failures"] == 0,
        "program_limits_respected": max(map(int, statistics["program_line_distribution"])) <= MAX_PROGRAM_LINES,
        "split_sizes_40_10_10": statistics["split_sizes"] == {"train": 40, "validation": 10, "test": 10},
    }
    checks["passed"] = all(checks.values())
    return checks


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_report(
    directory,
    statistics,
    checks,
    problems,
    manifest,
    test_results=None,
):
    examples = sorted(problems, key=lambda p: p.hardening["cognitive_family"])
    lines = [
        "# 认知多样性冒烟数据报告",
        "",
        "## 结论",
        "",
        "本产物用一套 60 道程序合成原型冒烟数据替代原先三套层叠产物。每道题对应一个不同语义原型；没有用字符改名、参数替换或题面改写凑数量。",
        "",
        "- 程序合成题：%d" % statistics["synthesis_problem_count"],
        "- 认知算法族：%d" % statistics["cognitive_family_count"],
        "- 语义原型：%d" % statistics["semantic_archetype_count"],
        "- 行为重复：%d" % statistics["behavior_duplicates"],
        "- alpha 等价题：%d" % statistics["alpha_equivalent_problem_count"],
        "- 参考程序验证：%.0f%%" % (100 * statistics["reference_verification_fraction"]),
        "- 有效组合题：%d（%.2f%%）"
        % (
            statistics["genuine_composition_count"],
            100 * statistics["genuine_composition_fraction"],
        ),
        "- 组件消融失败：%d"
        % statistics["composition_component_probe_failures"],
        "- 验收：%s" % ("通过" if checks["passed"] else "未通过"),
        "",
        "这 60 道题用于先审阅每族三个语义原型，不冒充最终 240 道正式程序合成数据。题面通过审阅后，才能为已批准原型实现参数生成和受控泛化评测。",
        "",
        "## 认知算法族分布",
        "",
        "| 认知算法族 | 数量 |",
        "|---|---:|",
    ]
    lines.extend("| `%s` | %d |" % item for item in statistics["cognitive_family_distribution"].items())
    lines.extend(["", "## 来源与领域", "", "- 来源类型（`source_type`）：`%s`" % json.dumps(statistics["source_type_distribution"], ensure_ascii=False), "- 任务领域（`task_domain`）：`%s`" % json.dumps(statistics["task_domain_distribution"], ensure_ascii=False), "- 组合深度（`composition_depth`）：`%s`" % json.dumps(statistics["composition_depth_distribution"], ensure_ascii=False), "", "## 每族代表题", ""])
    seen = set()
    for problem in examples:
        family = problem.hardening["cognitive_family"]
        if family in seen:
            continue
        seen.add(family)
        lines.extend(["### `%s`" % family, "", problem.generated_program.description, ""])
    lines.extend(
        [
            "## 质量统计",
            "",
            "- 恒等行为比例均值（`identity_fraction`）：%.4f"
            % statistics["identity_fraction_mean"],
            "- 常量行为比例均值（`constant_fraction`）：%.4f"
            % statistics["constant_fraction_mean"],
            "- 终止比例（`terminating_fraction`）：%.4f"
            % statistics["terminating_fraction"],
            "- 公开/隐藏测试重叠：%d"
            % statistics["public_hidden_overlap"],
            "- 执行步数：`%s`"
            % json.dumps(statistics["execution_steps"], ensure_ascii=False),
            "",
            "## 基线结果",
            "",
            "| 切分 | 基线 | 尝试数 | 通过公开测试 | 通过隐藏测试 | 只拟合公开测试 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for split, results in statistics["baseline_by_split"].items():
        for result in results:
            lines.append(
                "| %s | %s | %d | %d | %d | %d |"
                % (
                    split,
                    result["baseline"],
                    result["attempted"],
                    result["public_solved"],
                    result["hidden_solved"],
                    result["public_only_overfit"],
                )
            )
    lines.extend(["", "## 测试结果", ""])
    if test_results:
        lines.extend(
            [
                "- 通过：%d" % test_results["passed"],
                "- 失败：%d" % test_results["failed"],
                "- 跳过：%d" % test_results["skipped"],
                "- 用时：%s" % test_results["duration"],
            ]
        )
    else:
        lines.append("尚未通过 `dataset-report` 记录本次完整测试结果。")
    lines.extend(["", "## 验收检查", ""])
    lines.extend("- [%s] `%s`" % ("x" if value else " ", name) for name, value in checks.items() if name != "passed")
    lines.extend(
        [
            "",
            "## 当前限制",
            "",
            "- 这是 60 道语义原型审阅集，不是最终 240 道训练集。",
            "- 其中 35 道直接复用人工题，来源类型尚未达到正式训练集的平衡要求。",
            "- 尚未运行真实教师模型；教师结果不参与本次原型门禁。",
            "- 受控的参数留出、描述风格和长度配对评测要在原型审阅通过后生成。",
        ]
    )
    lines.extend(
        [
            "",
            "## 命令",
            "",
            "```text",
            manifest["commands"]["generation"],
            manifest["commands"]["audit"],
            manifest["commands"]["training_tests"],
            manifest["commands"]["interpreter_tests"],
            manifest["commands"]["report"],
            "```",
            "",
        ]
    )
    (directory / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_cognitive_smoke(root, output, *, seed=DEFAULT_SEED):
    root, output = Path(root), Path(output)
    problems = generate_cognitive_smoke(root, seed=seed)
    splits = split_cognitive(problems, seed=seed)
    split_by_problem = {problem.id: name for name, values in splits.items() for problem in values}
    auxiliary = generate_auxiliary_tasks(problems, seed=seed + 1, split_by_problem=split_by_problem)
    statistics = cognitive_statistics(problems, splits, auxiliary)
    checks = cognitive_checks(statistics)
    manifest = {
        "pipeline": "cognitive-dataset-smoke",
        "seed": seed,
        "rules": "training/DATASET_GENERATION_RULES.md",
        "rules_version": RULES_VERSION,
        "synthesis_problem_count": len(problems),
        "review_gate": True,
        "bulk_generation_started": False,
        "limits": {"max_program_lines": MAX_PROGRAM_LINES, "max_program_characters": MAX_PROGRAM_CHARACTERS},
        "commands": {
            "generation": "python3 -m training.cli dataset-generate --seed %d --output %s" % (seed, output),
            "audit": "python3 -m training.cli dataset-audit --artifact-dir %s" % output,
            "report": "python3 -m training.cli dataset-report --artifact-dir %s --passed TEST_COUNT --duration SECONDS" % output,
            "training_tests": "python3 -m unittest discover -s training/tests -v",
            "interpreter_tests": "python3 -m unittest -v test",
        },
    }
    if output.exists():
        shutil.rmtree(output)
    for name in ("private", "public", "auxiliary"):
        (output / name).mkdir(parents=True, exist_ok=True)
    for split, values in splits.items():
        write_jsonl(output / "private" / (split + ".jsonl"), (p.to_task_record() for p in values), validator=validate_cognitive_task)
        write_jsonl(output / "public" / (split + ".jsonl"), ({"id": p.id, "description": p.generated_program.description, "public_tests": list(p.public_tests)} for p in values))
    for name, records in auxiliary.items():
        by_split = {}
        for record in records:
            by_split.setdefault(record["split"], []).append(record)
        for split, values in by_split.items():
            target = output / "auxiliary" / split
            target.mkdir(parents=True, exist_ok=True)
            write_jsonl(target / (name + ".jsonl"), values)
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "statistics.json", statistics)
    _write_json(output / "exit_checks.json", checks)
    audit = audit_cognitive_smoke(output)
    _write_report(output, statistics, checks, problems, manifest)
    return {"manifest": manifest, "statistics": statistics, "checks": checks, "audit": audit}


def record_cognitive_test_results(
    directory,
    *,
    passed,
    failed,
    skipped,
    duration,
):
    directory = Path(directory)
    test_results = {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "duration": duration,
    }
    _write_json(directory / "test_results.json", test_results)
    manifest = json.loads(
        (directory / "manifest.json").read_text(encoding="utf-8")
    )
    statistics = json.loads(
        (directory / "statistics.json").read_text(encoding="utf-8")
    )
    checks = json.loads(
        (directory / "exit_checks.json").read_text(encoding="utf-8")
    )
    problems = []
    for split in ("train", "validation", "test"):
        problems.extend(
            GeneratedProblem.from_task_record(record)
            for record in read_jsonl(
                directory / "private" / (split + ".jsonl"),
                validator=validate_cognitive_task,
            )
        )
    _write_report(
        directory,
        statistics,
        checks,
        problems,
        manifest,
        test_results=test_results,
    )
    return directory / "REPORT.md"


def audit_cognitive_smoke(directory):
    directory = Path(directory)
    records = []
    split_by_root = {}
    for split in ("train", "validation", "test"):
        values = read_jsonl(directory / "private" / (split + ".jsonl"), validator=validate_cognitive_task)
        records.extend(values)
        split_by_root.update({record["id"]: split for record in values})
    failures = []
    behavior = Counter(record["concrete_behavior_fingerprint"] for record in records)
    alpha = Counter(record["alpha_equivalence_class"] for record in records)
    for record in records:
        if len(record["reference_programs"][0].splitlines()) > MAX_PROGRAM_LINES or len(record["reference_programs"][0]) > MAX_PROGRAM_CHARACTERS:
            failures.append(record["id"] + ":program_limit")
        program = parse(record["reference_programs"][0])
        for case in record["public_tests"] + record["hidden_tests"]:
            outcome = execute_with_limits(program, case["input"], max_steps=100000, max_length=MAX_RUNTIME_STRING_LENGTH)
            if not outcome.terminating or outcome.output != case["output"]:
                failures.append(record["id"] + ":reference_mismatch")
                break
    auxiliary_cross_split = 0
    for path in sorted((directory / "auxiliary").glob("*/*.jsonl")):
        split = path.parent.name
        for record in read_jsonl(path):
            root = record["root_problem_id"]
            if root in split_by_root and split_by_root[root] != split:
                auxiliary_cross_split += 1
    checks = {
        "record_count": len(records),
        "validation_failures": failures,
        "behavior_duplicates": sum(count - 1 for count in behavior.values() if count > 1),
        "alpha_equivalent_duplicates": sum(count - 1 for count in alpha.values() if count > 1),
        "auxiliary_reference_cross_split": auxiliary_cross_split,
    }
    checks["passed"] = len(records) == 60 and not failures and not checks["behavior_duplicates"] and not checks["alpha_equivalent_duplicates"] and not auxiliary_cross_split
    _write_json(directory / "audit.json", checks)
    return checks
