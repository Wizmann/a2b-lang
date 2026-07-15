# 题目与测试数据规则

## 题目 ID 与目录

- 题目 ID 使用 `1-1`、`1-2` 这类格式。
- 每题独占一个目录：`tasks/<题目 ID>/`。

## 每题必备文件

```text
tasks/<题目 ID>/
├── TASK.md
├── task.jsonl
├── solution.a2b
├── groundtruth.py
├── generate.py
├── testcase_pretest.jsonl
└── testcase_full.jsonl
```

- `TASK.md`：题面 Markdown，包含输入、输出、限制条件和全部样例。
- `task.jsonl`：题面 JSONL；一行一个 JSON 对象，至少包含 `id`、`input`、`output`、`constraints`、`samples`。题面中的输入、输出、限制条件和全部样例必须在同一对象内。
- `solution.a2b`：用户提供并确认正确的 A=B 语言解法。
- `groundtruth.py`：Python 参考实现；应提供可导入的 `solve(value)` 函数，并可从标准输入读取一行、向标准输出写出结果。
- `generate.py`：可复现的随机数据生成器。随机性必须使用固定种子，并能重新生成完整测试集。

## 测试集格式

测试数据使用 JSONL：每行是一个测试对象，且必须恰好包含 `input` 与 `output` 两个字段。例如：

```json
{"input":"abc","output":"bbc"}
```

- `testcase_pretest.jsonl`：小型预测试集，恰好 10 条，全部手工设计，用于基本功能和关键边界。
- `testcase_full.jsonl`：完整测试集，恰好 220 条：前 20 条为手工设计的数据，后 200 条为随机生成的数据。

手工数据应覆盖题目边界、最小/最大规模、特殊值、典型值和样例；随机数据必须满足题面约束。

## 验证要求

生成完成后，必须对完整集的全部 220 条输入逐条验证：

1. `groundtruth.py` 的结果等于 JSONL 中 `output` 字段记录的期望输出。
2. `solution.a2b` 通过仓库的 A=B 解释器执行后的结果等于 ground truth。

只有全部数据一致时，题目数据才可提交 review。
