# 01 — Full Shell Screening Agent Workflow Overview

> **先看这个文件。这个文件讲的是完整 Agent workflow，不是 PCE workflow。**

## 1. 总体定位

本项目的主产品是 **HK Shell Screening Agent**：它用于从港股上市公司中筛选潜在重组 / 壳资源 / 收购候选，并形成可审计、可复核、可交付的研究轨迹。

PCE 的角色是后置 governance / certification gate：

> Agent 可以生成候选名单和研究报告，但 **生成并不等于许可**。只有完整研究轨迹通过 PCE 认证后，才允许进入最终交付。

## 2. 完整 workflow

| Step | Stage | What happens | Output |
| --- | --- | --- | --- |
| 0 | Mandate & transaction boundary | 明确用户目标、市场范围、筛选目的、交付边界 | case input, mandate record |
| 1 | Source hierarchy & data access | 定义数据源优先级和允许使用范围 | source map, source inventory |
| 2 | Universe construction | 构建港股候选池 | candidate universe table |
| 3 | Extraction & normalization | 抽取并标准化 market cap、P/B、turnover、上市状态、公告/证据字段 | raw/interim/processed tables |
| 4 | Hard Filter + HF-level ER/BRB | 做硬筛；ER/BRB 在这里融合初筛证据，形成 pass / exclude / watchlist / DD escalation | hard filter table, exclusion reasons, ER/BRB hard-filter rows |
| 5 | Filtered candidate set | 形成进入 DD 的候选集 | candidate DD scaffold, shortlist draft |
| 6 | Deep Due Diligence + DD-level ER/BRB | 做控制权、债务诉讼、合规、公告正文、carrying cost 等深度尽调；ER/BRB 在这里聚合深层风险 | DD evidence table, risk matrix, DD review pack |
| 7 | Scoring / ranking / recommendation draft | 生成候选排序、case study draft、final report draft | reports, case study, proposed recommendation |
| 8 | Certified Research Trace | 把 mandate、source、retrieval、universe、HF、DD、ER/BRB、计算、claim、人审串成一条 trace | certified research trace folder |
| 9 | PCE Certification Gate | 认证完整研究轨迹是否允许交付 | audit spreadsheet, certification report, decision |
| 10 | Execution / Final Delivery | 只释放 certified claims 支撑的最终材料 | final certificate, report, DD pack |

## 3. 读者应该如何理解 PCE

PCE 不是替代 Agent 主流程，也不是把项目变成“只有认证表”。它只是保证：

- Agent 的候选名单不是凭空来的；
- 每个关键结论能追溯到 source / evidence / calculation / risk / review；
- final report 不会绕过 trace 直接交付；
- 不确定、重大风险或证据不足的地方必须被标注或升级。

## 4. 推荐演示说法

> “这个系统先运行 Shell Screening Agent：构建 universe、做 hard filter、做 DD、用 ER/BRB 在 hard filter 和 DD 两个阶段分别融合证据并校准判断。然后系统把整个研究过程保存为 Certified Research Trace。PCE 不是主流程，而是最后的认证闸门：它检查这条 trace 是否足够可靠，只有通过后才允许进入 final delivery。”

对应表格见：`full_workflow_tables.xlsx`。
