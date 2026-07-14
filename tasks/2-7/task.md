# 2-7：上升

## 输入

一个仅由 `a`、`b`、`c` 组成的字符串。

## 输出

当且仅当 `a`、`b`、`c` 的出现次数严格递增，即 `count(a) < count(b) < count(c)` 时，输出 `true`；否则输出 `false`。

## 限制条件

- `1 <= 输入长度 <= 7`
- 挑战目标：A=B 程序最多 8 行。

## 样例

| Input | Output |
| --- | --- |
| `abbccc` | `true` |
| `cccbb` | `true` |
| `abacc` | `false` |
