# 02 — ER/BRB in the Full Workflow

ER/BRB 不是一个单独放在最后的“评分表”，而是完整 Shell Screening Agent 里的跨阶段决策引擎。

## 两个触点

| Touchpoint | Stage | Role | Output |
| --- | --- | --- | --- |
| HF-level ER/BRB | Hard Filter | 在初筛信息不完整、来源可靠性不同、信号有噪声的情况下，把 evidence 融合成 pass / exclude / watchlist / DD escalation + confidence | hard-filter decision, confidence, DD escalation |
| DD-level ER/BRB | Deep Due Diligence | 在更多文件级证据出现后，对 litigation、debt、control、compliance、carrying cost 等风险重新聚合，校准 reranking 和 recommendation | DD-adjusted risk, reranking, recommendation support |

## 关键边界

- HF-level ER/BRB 不能把真正的 hard exclusion 洗成 pass。
- DD-level ER/BRB 不是重复 hard filter；它是更深证据下的二次判断。
- DD-level ER/BRB 可以确认、修正或推翻 HF 阶段的 provisional 判断。
- PCE 要检查两个 ER/BRB 触点是否都有 rule、source、rationale、claim linkage 和 human review flag。
