# 03 — PCE as One Module, Not the Whole Product

## 正确关系

```text
Shell Screening Agent 主流程
  -> Certified Research Trace
  -> PCE Certification Gate
  -> Certified Execution
```

PCE 是认证装置，不是整个产品。

## PCE 检查什么

| Area | What PCE checks |
| --- | --- |
| Mandate | 是否遵守用户委托和交付边界 |
| Sources | 数据源是否合规、来源优先级是否清楚 |
| Universe | 候选池构建是否可追溯 |
| Hard Filter | retain/exclude/watchlist 是否有规则和来源 |
| HF-level ER/BRB | hard filter 阶段 ER/BRB 的证据融合是否有 rationale 和置信度 |
| DD Evidence | material claims 是否有文件/表格证据 |
| DD-level ER/BRB | DD 阶段风险聚合、reranking、recommendation 是否有证据支撑 |
| Calculation | 数值计算是否 replayed |
| Claim map | 报告中的 claim 是否映射 evidence / calc / risk / review |
| Human review | 重大风险和不确定性是否被升级 |
| Execution | 最终交付是否只使用 certified claims |

## PCE 不做什么

- 不替代 Agent 的 universe construction / HF / DD 主流程。
- 不替代律师、税务、监管、投委会或董事会判断。
- 不把“生成出来的报告”自动变成“可以交付”。
