# 认知多样性冒烟数据报告

## 结论

本产物用一套 60 道程序合成原型冒烟数据替代原先三套层叠产物。每道题对应一个不同语义原型；没有用字符改名、参数替换或题面改写凑数量。

- 程序合成题：60
- 认知算法族：20
- 语义原型：60
- 行为重复：0
- alpha 等价题：0
- 参考程序验证：100%
- 有效组合题：10（16.67%）
- 组件消融失败：0
- 验收：通过

这 60 道题用于先审阅每族三个语义原型，不冒充最终 240 道正式程序合成数据。题面通过审阅后，才能为已批准原型实现参数生成和受控泛化评测。

## 认知算法族分布

| 认知算法族 | 数量 |
|---|---:|
| `boundary_transform` | 3 |
| `bounded_occurrence_edit` | 3 |
| `carry_borrow_arithmetic` | 3 |
| `conditional_transform` | 3 |
| `copy_and_reuse` | 3 |
| `count_argextreme` | 3 |
| `count_threshold` | 3 |
| `delimiter_field_logic` | 3 |
| `endpoint_relation` | 3 |
| `merge_and_deinterleave` | 3 |
| `modular_property` | 3 |
| `ordering_partition` | 3 |
| `palindrome_and_pairing` | 3 |
| `pointwise_transform` | 3 |
| `positional_expansion` | 3 |
| `positional_selection` | 3 |
| `representation_arithmetic` | 3 |
| `reversal_symmetry_transform` | 3 |
| `run_structure` | 3 |
| `segment_movement` | 3 |

## 来源与领域

- 来源类型（`source_type`）：`{"composed": 10, "enumerated": 2, "handwritten": 35, "template": 13}`
- 任务领域（`task_domain`）：`{"counting_classification": 9, "delimited_fields": 3, "numeric_representation": 6, "relational_classification": 9, "sequence_construction": 12, "sequence_reordering": 9, "string_rewrite": 12}`
- 组合深度（`composition_depth`）：`{"1": 50, "2": 10}`

## 每族代表题

### `boundary_transform`

输入：一个仅由 a、b、c 组成的字符串。
输出：将输入头部和尾部的每个连续 a 替换为 b；中间部分保持不变。
限制：长度为 1 到 7。

### `bounded_occurrence_edit`

输入：一个仅由 a、b、c 组成的字符串。
输出：移除输入中最靠左的三个 a；如果输入少于三个 a，则移除全部 a。
限制：长度为 1 到 7。

### `carry_borrow_arithmetic`

输入：一个二进制数（不含前导零）。
输出：输入二进制数加 1 后的二进制表示。

### `conditional_transform`

输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。
输出：如果输入包含 `b`，删除所有 `a`；否则保持原字符串不变。

### `copy_and_reuse`

输入：一个由 `a`、`b`、`c` 组成的非空字符串，长度不超过 8。
输出：在原字符串末尾再添加一次首字符。

### `count_argextreme`

输入：一个仅由 a、b 组成的字符串。
输出：输出出现次数更多的字母。
限制：长度为 1 到 11。

### `count_threshold`

输入：一个仅由 a、b、c 组成的字符串。
输出：如果输入包含至少三个 a，输出 true；否则输出 false。
限制：长度为 1 到 7。

### `delimiter_field_logic`

输入：两个非空一元字符串，以逗号分隔，例如 `aaa,aa`。
输出：逗号左侧的字符串。

### `endpoint_relation`

输入：一个由 `a`、`b`、`c` 组成的非空字符串，长度不超过 8。
输出：字符串的第一个字符。

### `merge_and_deinterleave`

输入：两个仅由 a、b 组成且长度相同的字符串，以逗号隔开。
输出：将两个字符串的字母交替合并。
限制：长度为 1 到 5；两个字段长度相同。

### `modular_property`

输入：一个仅由 a、b、c 组成的字符串。
输出：如果输入中每个字母的出现次数均为奇数或 0，输出 true；否则输出 false。
限制：长度为 1 到 7。

### `ordering_partition`

输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。
输出：稳定地将所有 `b` 移到末尾，`a` 和 `c` 的相对顺序保持不变。

### `palindrome_and_pairing`

输入：一个仅由 a、b、c 组成的字符串。
输出：如果输入正向和反向读起来相同，输出 true，否则输出 false。
限制：长度为 1 到 7。

### `pointwise_transform`

输入：一个仅由 a、b、c 组成的字符串。
输出：将输入中的每个 a 替换为 b 后的字符串。
限制：长度为 1 到 7。

### `positional_expansion`

输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。
输出：奇数位置的字符输出两次，偶数位置的字符输出一次。

### `positional_selection`

输入：一个仅由 a、b、c 组成的字符串。
输出：移除第三个字母。
限制：长度为 3 到 7。

### `representation_arithmetic`

输入：一个二进制数（不含前导零）。
输出：输出与该二进制数数值相等数量的 a。

### `reversal_symmetry_transform`

输入：一个仅由 `a`、`b`、`c` 组成的字符串，可以为空，长度不超过 8。
输出：删除所有 `c`，再反转剩余字符串。

### `run_structure`

输入：一个仅由 a、b、c 组成的字符串。
输出：将每段连续的相同字母替换为该字母本身的单个字符。
限制：长度为 1 到 7。

### `segment_movement`

输入：一个由 a、b、c 组成且至少包含一个 a 的字符串。
输出：将第一个 a 之前的所有字符移动到字符串末尾。
限制：长度为 1 到 7。

## 质量统计

- 恒等行为比例均值（`identity_fraction`）：0.0949
- 常量行为比例均值（`constant_fraction`）：0.1852
- 终止比例（`terminating_fraction`）：1.0000
- 公开/隐藏测试重叠：0
- 执行步数：`{"maximum": 99, "mean": 9.78800170794193, "minimum": 0}`

## 基线结果

| 切分 | 基线 | 尝试数 | 通过公开测试 | 通过隐藏测试 | 只拟合公开测试 |
|---|---|---:|---:|---:|---:|
| test | identity | 10 | 0 | 0 | 0 |
| test | constant | 10 | 0 | 0 | 0 |
| test | single_rule_search | 10 | 0 | 0 | 0 |
| test | template_search | 10 | 0 | 0 | 0 |
| train | identity | 40 | 0 | 0 | 0 |
| train | constant | 40 | 0 | 0 | 0 |
| train | single_rule_search | 40 | 1 | 1 | 0 |
| train | template_search | 40 | 3 | 3 | 0 |
| validation | identity | 10 | 0 | 0 | 0 |
| validation | constant | 10 | 0 | 0 | 0 |
| validation | single_rule_search | 10 | 0 | 0 | 0 |
| validation | template_search | 10 | 0 | 0 | 0 |

## 测试结果

- 通过：98
- 失败：0
- 跳过：0
- 用时：41.342s

## 验收检查

- [x] `alpha_equivalent_fraction_zero`
- [x] `behavior_duplicates_zero`
- [x] `cognitive_families_20`
- [x] `composition_components_all_effective`
- [x] `genuine_composition_fraction_15_to_25_percent`
- [x] `operational_descriptions_zero`
- [x] `program_limits_respected`
- [x] `reference_verification_100_percent`
- [x] `split_sizes_40_10_10`
- [x] `synthesis_archetypes_60`
- [x] `three_archetypes_per_family`

## 当前限制

- 这是 60 道语义原型审阅集，不是最终 240 道训练集。
- 其中 35 道直接复用人工题，来源类型尚未达到正式训练集的平衡要求。
- 尚未运行真实教师模型；教师结果不参与本次原型门禁。
- 受控的参数留出、描述风格和长度配对评测要在原型审阅通过后生成。

## 命令

```text
python3 -m training.cli dataset-generate --seed 20260715 --output training/artifacts/dataset_smoke
python3 -m training.cli dataset-audit --artifact-dir training/artifacts/dataset_smoke
python3 -m unittest discover -s training/tests -v
python3 -m unittest -v test
python3 -m training.cli dataset-report --artifact-dir training/artifacts/dataset_smoke --passed TEST_COUNT --duration SECONDS
```
