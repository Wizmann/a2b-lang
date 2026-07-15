# A=B 训练数据生成规则

状态：现行规则。生成器与数据审计必须遵守本文；规则变更需要单独 review。

## 1. 目标

训练集要覆盖不同的计算思想，而不是覆盖许多不同的字符、常量、转移表或题面措辞。

本设计借鉴 `tasks/` 和算法题的出题原则：

- 题面直接定义输入到输出的函数，不复述 A=B 规则；
- 每题有明确的关键关系、不变量或需要维护的信息；
- 公开样例解释语义，隐藏测试检查泛化；
- 输入规模足以排除枚举测试集和只对短输入成立的程序；
- 难度来自算法语义，而不是冗长题面或随机转移表；
- 只有改变解题所需信息或核心不变量，才算新的认知题型。

LeetCode 题目的规模通常不适合直接搬到 A=B。这里借鉴的是“问题由语义和关键不变量定义”，不是照搬数组、图、动态规划等复杂题型。

## 2. 四层分类

每道 synthesis 题同时记录以下四层。只有 `cognitive_family` 和 `semantic_archetype` 能用于认知多样性计数。

### 2.1 task_domain

题目的表面对象，例如：

- `plain_string`
- `delimited_fields`
- `unary_number`
- `binary_number`
- `encoded_string`

领域不同不代表算法不同。二进制串反转和普通字符串反转仍是同一个认知算法族。

### 2.2 cognitive_family

完成题目必须掌握的主要计算思想。每题恰好有一个主族，可以有多个辅助 concepts。

例如“统计出现次数最多的字符并只保留它”属于 `count_argextreme`，过滤只是输出阶段的辅助概念。

### 2.3 semantic_archetype

同一认知族中的不同语义关系，例如：

- `count_argextreme/return_winner`
- `count_argextreme/keep_winner_occurrences`
- `count_argextreme/compare_strict_order`

换字母、换阈值、换 alphabet、换 marker、换最大输入长度，不产生新的 semantic archetype。

### 2.4 parameter_instance

某个语义原型的具体参数实例，只用于增加覆盖面，不计作新的题型。

例如“至少三个 `a`”和“至少两个 `b`”通常只是同一原型的两个参数实例。

## 3. 认知签名

每题生成以下机器可审计字段：

```text
cognitive_family
semantic_archetype
information_scope
memory_model
traversal_model
output_shape
primary_invariant
cognitive_signature
```

建议枚举：

- `information_scope`：`local | boundary | positional | global | multi_field`
- `memory_model`：`none | bounded_counter | parity_state | symbol_counter | finite_state | marker_workspace | carry_borrow`
- `traversal_model`：`pointwise | left_to_right | right_to_left | bidirectional | repeated_rewrite`
- `output_shape`：`same_length | filtered | expanded | scalar | boolean | reordered | multi_field`

`cognitive_signature` 是以上字段与规范化 semantic IR 的组合。它用于发现两个不同 generator 名称实际上仍在生成同一种题。

## 4. 候选认知算法族

下面定义 24 个候选族。首轮 smoke 不要求为了凑数强行实现全部族，但正式验收要求至少 20 个族可靠地产生样本。

### A. 局部与连续结构

#### F01 pointwise_transform：逐字符变换

每个输出字符只依赖对应输入字符。

可用原型：字符置换、大小写/符号表转换、按类别映射。

不计新原型：只把 `a→b` 改成 `x→y`；把 encoder 改名为 mapper。

#### F02 local_context_rewrite：局部上下文变换

输出取决于相邻字符或短窗口，但不需要全局计数。

可用原型：替换互不重叠的目标串、删除夹在两个相同字符之间的字符、根据前一字符改变当前字符。

#### F03 run_structure：连续段分析

以最大连续相同字符段为基本对象。

可用原型：压缩连续段、删除长度至少为二的指定字符段、保留奇数长度段、判断单字符段数量。

#### F04 boundary_transform：首尾与边界段处理

只处理头部、尾部或两侧最大连续段。

可用原型：去掉两端指定字符、替换两端字符、交换首尾连续段、比较首尾字符。

#### F05 bounded_occurrence_edit：按出现次序编辑

需要区分第一个、最后一个、前 k 个或后 k 个匹配项。

可用原型：删除最左侧三个 `a`、删除最后两个 `b`、替换首次出现、保留第 k 次出现。

改变 k 只是参数变化；“最左侧”与“最右侧”可以属于不同 semantic archetype，但仍属于同一族。

### B. 顺序、位置与重排

#### F06 ordering_partition：排序与稳定分组

需要维护全局次序关系。

可用原型：有限 alphabet 排序、按字符类别稳定分区、将满足条件的字符稳定移到前面。

#### F07 segment_movement：区段移动

移动完整区段而不是独立映射字符。

可用原型：旋转到首次出现的分隔字符、交换头尾连续段、移动指定分隔符前的前缀、循环移位。

#### F08 positional_selection：位置选择与删除

输出依赖索引或相对位置。

可用原型：保留偶数位置、删除第 k 个字符、取中间字符、删除中间字符、保留每三个字符中的第一个。

#### F09 positional_expansion：位置相关扩张

每个字符的输出次数依赖位置。

可用原型：第 i 个字符重复 i 次、奇数位置复制两次、按周期 `1,2,1,2` 扩张。

#### F10 reversal_symmetry_transform：反转与对称变换

需要从两端建立对应关系。

可用原型：完整反转、交换首尾字符、逐对交换对称位置、反转每个分隔字段。

普通字符串反转与二进制串反转是同一 semantic archetype。

### C. 全局统计与判定

#### F11 count_threshold：计数阈值与精确计数

需要计数某类符号并与常量比较。

可用原型：至少出现 k 次、恰好出现 k 次、出现次数位于区间、恰好 k 个 singleton run。

#### F12 count_argextreme：频数比较与极值

需要比较两个或多个符号的出现次数。

可用原型：输出唯一最多字符、只保留最多字符、判断 `count(a)<count(b)<count(c)`、输出较少者。

#### F13 modular_property：奇偶性与模运算

只需保留计数或长度的有限余数状态。

可用原型：输出长度模 k、判断每类字符计数的奇偶性、按索引模 k 分类输出。

#### F14 endpoint_relation：端点关系判定

比较首字符、尾字符或首尾类别。

可用原型：首尾是否相同、首尾是否属于同一类别、首字符是否等于唯一最多字符。

#### F15 palindrome_and_pairing：镜像配对判定

需要反复比较两端或构造镜像对应。

可用原型：回文判定、忽略某类字符后的回文判定、每对镜像字符是否不同。

#### F16 pattern_order_relation：模式与相对次序

关注符号出现的先后或子序列关系，不只是固定子串是否存在。

可用原型：是否存在 `a…b…c` 子序列、所有 `a` 是否都在 `b` 前、指定模式出现次数是否唯一。

单纯“包含某个随机子串”的参数实例应严格限量。

### D. 有状态和条件计算

#### F17 semantic_finite_state_scan：有语义的有限状态扫描

使用有限状态，但题面描述一个自然性质，不给随机转移表让模型照抄。

可用原型：相邻字符必须交替、禁止连续出现某模式、按当前位置奇偶选择映射、扫描转义字符。

随机 DFA/FST 转移表保留为少量鲁棒性数据，不计作多个认知族或多个 archetype。

#### F18 conditional_transform：全局条件控制变换

先判断全局性质，再选择不同输出函数。

可用原型：若包含 `b` 则 `a→b`，否则 `a→c`；若长度为奇数则反转，否则保持；按多数字符选择保留策略。

条件必须实质影响输出，且两个分支都要有充分测试。

#### F19 delimiter_field_logic：分隔字段处理

输入含两个或多个字段，需要保持字段边界并建立字段关系。

可用原型：分别变换逗号两侧、比较两字段长度、交换字段、对齐后逐位选择。

仅把单串题外面加一个无用字段不算新题型。

### E. 构造、复制与编码

#### F20 copy_and_reuse：复制并复用输入信息

需要保存输入的一部分并再次输出。

可用原型：复制整个字符串、复制前三个字符到末尾、输出 `reverse(s)+s`、复制指定边界段。

#### F21 merge_and_deinterleave：交错合并与拆分

需要在多个序列之间交替搬运信息。

可用原型：等长字符串交错合并、将奇偶位置拆成两个字段、按对成组交换、两个字段逐位配对。

#### F22 structured_codec：结构化编码与解码

编码必须表示结构，而非逐字符换 alphabet。

可用原型：小计数范围的 run-length encoding、成对编码/解码、对重复字符使用转义、有限 alphabet 的可逆分组编码。

单纯 `a→u,b→v` 属于 F01，不属于 codec。

### F. 数值计算

#### F23 representation_arithmetic：表示转换与一元运算

需要解释整个字符串表示的数值。

可用原型：二进制转一元、有限 alphabet 进制转换、一元加减、输出 popcount 的一元表示。

#### F24 carry_borrow_arithmetic：带进位/借位的算术

需要传播进位或借位。

可用原型：二进制加一、二进制减一、二进制加法、二进制减法。

乘法只有在参考程序满足长度上限时才进入 hard 集。当前 `tasks/5-6` 的除法解法为 39 行，超过 32 行上限，暂不进入本轮生成范围。

## 5. 组合不是第 25 个表面题型

`composition_depth` 是正交维度，不单独充当认知多样性。只有组件发生语义交互，组合才计入 `genuine_composition`。

合格例子：

- 删除两端的 `a`，再返回剩余字符串的中间字符；第一阶段会改变第二阶段选择的位置。
- 找出唯一最多字符，只保留该字符，再把保留结果编码为一元长度；第二阶段消费第一阶段的统计结果。
- 将两个字段交错合并，再判断结果是否为回文；不能分别对两个输入字段求值后简单拼接。
- 先按连续段压缩，再保留偶数位置；压缩改变后续位置编号。

不合格或降级例子：

- `map → map`，可合并成一次映射；
- `delete(a) → delete(b)`，可合并成一次过滤；
- `reverse → reverse`，等价于 identity；
- 两个阶段作用于互不相关的字符且可以交换顺序；
- 题面只是逐条列出内部实现过程。

组合题应优先使用直接的函数语义描述。例如写“删除两端所有 `a` 后，输出剩余字符串的中间字符”，不要写“一台机器先执行……再执行……”，也不要用“操作顺序”充当题目语义。

## 6. 不计入认知多样性的变化

以下变化可以用于鲁棒性 benchmark，但不能提高 diversity 分数：

- 输入字符、内部 marker 或状态名重命名；
- 阈值、轮转距离、目标字符等常量变化；
- alphabet 大小变化；
- 最大输入长度变化；
- functional 题面的措辞变化；
- 同一 DFA/FST 结构更换随机转移表；
- 同一程序添加无效规则、死组件或可消除阶段；
- encoder、decoder、normalizer 等 generator 名称变化，但 oracle 仍是字符映射；
- 把普通字符串换成二进制字符后执行相同的反转、过滤或压缩。

固定输出、identity、直接复述规则的 operational 题可以用于基础能力或辅助任务，但不计入高质量 synthesis 的认知族覆盖。

## 7. 240 题 smoke 的建议配额

### 7.1 覆盖要求

- 至少 20 个 `cognitive_family` 有可靠样本；
- 至少 60 个 `semantic_archetype`；
- 每个启用的认知族至少 3 个 semantic archetype；
- 每个认知族 6～16 题，任何单族不超过总量的 7%；
- 每个 semantic archetype 最多 4 题；
- 任一认知大组 A～F 不超过总量的 25%；
- 至少 40% 的题来自旧 smoke 未实质覆盖的 archetype；
- genuine composition 占 15%～25%，其中至少 80% 不可化简且有组件交互；
- composition depth 3 的题必须三个组件都有效。

### 7.2 限制低价值数据

- `operational` description 不超过 5%，并单独报告，不计入高难 synthesis；
- 随机转移表 DFA/FST 合计不超过 5%；
- identity 与 constant transformation 不进入正式 synthesis；
- 简单 pointwise map、单字符 filter、固定 substring classifier 合计不超过 10%；
- alpha-equivalent 或纯参数换皮实例不超过正式 synthesis 的 2%，且只允许出现在专门的受控 benchmark 中；
- 同一个规范化 oracle/IR 结构簇最多 4 题。

### 7.3 程序与输入限制

- A=B 程序硬上限：32 行、512 字符；
- 默认目标：不超过 16 行、256 字符；
- 禁止按测试输入或有限输入全集枚举答案；
- 用 construction/public/hidden/generalization/audit 五个 domain 验证；
- 对可扩展语义，hidden 与 generalization 必须包含明显长于 public 的输入；
- 参考程序必须在长输入上保持正确并在 step/length limit 内终止；
- 不能仅因为 construction domain 很小，就把暴力枚举程序标为正确参考解。

## 8. 反换皮验收

每个候选题依次执行：

1. 规范化输入 alphabet、内部 marker、状态名和无语义常量；
2. 规范化 semantic IR 与 Python oracle AST；
3. 计算 `cognitive_signature` 与最近 semantic archetype；
4. 判断差异来自新语义，还是只来自参数、字符名或题面措辞；
5. 对组合题执行组件删除、交换与可化简分析；
6. 在长输入和对抗输入上比较 oracle 与 A=B 参考程序。

必须报告：

- cognitive family 分布；
- semantic archetype 分布；
- cognitive signature cluster 大小；
- parameter-only variant fraction；
- alpha-equivalent fraction；
- random-table fraction；
- operational fraction；
- genuine composition fraction；
- 旧 smoke 未覆盖 archetype 的比例；
- 每个族的代表题与最大结构簇。

如果字段统计达标但 semantic archetype 或 cognitive signature 仍集中，应判定 `diversity_acceptance_failed`。

## 9. 首轮实现优先级

### P0：已有 `tasks/` 证明 A=B 可可靠表达

F03、F04、F05、F06、F07、F08、F09、F10、F11、F12、F13、F14、F15、F18、F20、F21、F23、F24。

### P1：需要新增可靠 oracle/compiler

F02、F16、F17、F19、F22，以及 genuine composition。

### P2：本轮暂不强求

- 超过 32 行的除法；
- 为凑领域数而生成的随机机器表；
- 无法用简洁 functional description 表达的随机挖掘程序；
- 只有短输入穷举才能验证的复杂组合。

实现时先为每个 P0/P1 族手写 3 个 semantic archetype 并 review 题面，再写参数生成器。未通过题面 review 的族不进入批量生成。

## 10. Review 决策点

建议 review 时重点确认：

1. 24 个族是否切得过细或仍有同义重复；
2. 哪些 P1 原型不值得为 A=B 实现；
3. 240 题至少 20 个族、60 个 archetype 是否合适；
4. 单族上限 7%、单 archetype 上限 4 题是否足够严格；
5. structured codec、delimiter field、semantic finite-state scan 的题面是否自然；
6. 是否保留少量 operational/random-table 数据作为鲁棒性样本。

Review 通过前，不修改现有生成流水线，不重新生成 smoke 数据。
