# Trajectory Certification Report / 轨迹层认证报告

## 认证对象

- Trace ID：TRACE-TUNTUN-001
- Proposal object：candidate research trajectory
- Case：吨吨健康科技集团港股上市公司重组标的筛选

## 认证结论摘要

当前轨迹可进入 **Execution Layer**，但需在交付材料中清楚标注：这是通过 PCE 轨迹认证的 research package，不是最终交易意见书。

## Trajectory-level Checks

| Check | Result | Note |
| --- | --- | --- |
| Mandate / 交易边界 | Pass | mandate_record exists and delivery boundary is explicit |
| Source inventory / 来源清单 | Pass | 7 source rows available |
| Universe construction / 候选池构建 | Pass | 2741 candidate universe rows |
| Hard filters / 硬筛 | Pass with caveat | 2741 hard-filter rows; {'exclude': 2033, 'pass': 696, 'watchlist': 12} |
| **HF-level ER/BRB / 硬筛阶段证据融合** | Pass with caveat | ER/BRB participates inside Hard Filter: evidence reliability + belief distribution + pass/exclude/watchlist/DD escalation. PCE checks source/rule/rationale linkage. |
| Filtered candidate set / 过滤后候选 | Pass | pass/watchlist candidates are preserved for DD or recommendation workflow |
| DD evidence / 尽调证据 | Pass with caveat | 532 DD evidence rows; some title-level evidence remains internal trace only |
| **DD-level ER/BRB / DD 阶段风险聚合** | Pass with caveat | ER/BRB also participates inside DD/reranking: litigation, debt, control, compliance, carrying-cost and document evidence should affect final risk/recommendation. Scoring differentiation should be improved for presentation. |
| Calculation replay / 计算复现 | Pass | 10/10 required audit calculations replayed |
| Claim-evidence map / 主张证据映射 | Pass | 810 claim rows mapped |
| Human review gate / 人审 | Pass for current external scope | 0 audit rows require human review in current claim-level audit |
| Execution readiness / 执行许可 | Pass | 87 external_final rows certified; 0 non-certified rows |

## PCE Workflow Certification Table

| PCE layer | Certified object | What was checked | Certification output |
| --- | --- | --- | --- |
| Proposal | Agent-generated candidate research trajectory | mandate, universe, hard filters, HF-ER/BRB, DD evidence, DD-ER/BRB, proposed recommendation | Proposal accepted as certifiable object, not final delivery |
| Certification | Full trace + claim audit | source quality, evidence linkage, calculation replay, risk escalation, human review, ER/BRB traceability | Certified |
| Execution | final report / case study / DD pack | final deliverables only use certified claims and certified trace | Execution permitted with boundary note |

## 主要改进点

相较 v0.2，本版不再把 Excel 本身等同于 PCE，而是把 Excel 放在 Certification 层，作为 claim-level audit 的一个组件。真正的认证对象是完整研究轨迹。

相较 v0.3，本版进一步明确：ER/BRB 不是只放在某一个后置评分环节，而是在 **Hard Filter** 和 **Deep Due Diligence** 两个阶段都被调用。

## 残余不足

- 部分 Top 候选分数过于接近，展示时需要解释评分公式和区分度。
- 部分候选的公告正文读取、控制权路径确认和 Rule 14 风险仍应作为后续 DD 项。
- 管理层意愿、控制权交易可行性、监管态度等不能被自动认证为事实，只能作为 screening hypothesis。
