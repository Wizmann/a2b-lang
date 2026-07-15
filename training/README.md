# A=B 训练数据工具

本目录只负责数据生成、验证、切分、审计和辅助任务构造，不包含模型训练。
现有解释器和 `tasks/` 原题不会被数据工具改写。

数据生成规则见 [DATASET_GENERATION_RULES.md](DATASET_GENERATION_RULES.md)。

## 当前统一冒烟集

当前只维护一套认知原型冒烟数据：

- 60 道程序合成题；
- 20 个认知算法族；
- 每族 3 个不同语义原型；
- 不使用字符改名、常量替换或题面改写凑数量；
- 10 道经组件消融验证的两阶段组合题；
- 程序最多 32 行、512 字符；
- 所有期望输出由本地 Python oracle 或 `tasks/groundtruth.py` 产生；
- execution、trace、repair、completion 等辅助任务与根题保持同一切分。

这 60 道题是题面和语义原型的 review 门禁，不冒充最终的大规模训练集。
只有原型通过 review 后，才允许实现参数生成和受控泛化 benchmark。

## 命令

在仓库根目录执行：

```text
python3 -m training.cli dataset-generate \
  --seed 20260715 \
  --output training/artifacts/dataset_smoke

python3 -m training.cli dataset-audit \
  --artifact-dir training/artifacts/dataset_smoke

python3 -m unittest discover -s training/tests -v

python3 -m unittest -v test

python3 -m training.cli dataset-report \
  --artifact-dir training/artifacts/dataset_smoke \
  --passed TEST_COUNT \
  --duration SECONDS
```

## 产物结构

```text
training/artifacts/dataset_smoke/
├── private/          # 完整记录，含隐藏测试和参考程序
├── public/           # 只能用于构造模型 prompt 的公开视图
├── auxiliary/        # 本地执行器生成的辅助任务
├── manifest.json
├── statistics.json
├── exit_checks.json
├── audit.json
├── test_results.json
└── REPORT.md
```

prompt 只能读取 `public/` 中的字段。`hidden_tests`、参考程序、行为指纹、
lineage 和审计字段均不得进入模型输入。

## JSONL 与 schema

- 每行一个 JSON 对象；
- 读写时逐行验证；
- UTF-8 编码并保留 Unicode；
- 允许空字符串输入和输出；
- 未声明字段会被拒绝；
- 认知数据必须包含 `cognitive_family`、`semantic_archetype`、
  `cognitive_signature` 和相关信息依赖字段。

## 可复现性

所有随机选择只使用显式 seed 和注入的 RNG。相同代码、配置和 seed 应产生
相同的题目、切分和辅助任务。生成器会在写入前执行本地参考验证，审计命令会
从磁盘重新读取并再次执行全部公开与隐藏测试。
