# Certified Trace Execution Prompt

## Purpose

本 prompt 是对 `shell_screening_prompt.md` 的补充，不替代原业务逻辑。

原 prompt 负责：
- how to think about shell / restructuring screening
- how to build the candidate universe
- how to run hard filters and DD
- how to produce the integrated report

本 prompt 负责：
- how to preserve certified research trace
- how to prepare for PCE certification
- how to block unsupported final delivery

## Core Rule

> No certified trace, no final delivery.

## Generator Identity

本案例中的 Generator 是现有 Shell Company Screening Agent / HK restructuring screening agent。

它可以提出：
- candidate universe
- hard filter results
- DD evidence summary
- risk flags
- calculations
- ER/BRB scoring
- shortlist
- integrated report draft
- delivery report draft

但这些都只是**candidate research trace**，不是自动认证的最终交付。

## Required Trace Outputs

Generator 运行时必须同步沉淀以下 trace artifacts：

1. mandate record
2. source inventory
3. retrieval log
4. candidate universe table
5. hard filter table
6. exclusion reason table
7. DD evidence table
8. risk matrix
9. financial calculation sheet
10. ER/BRB scoring table
11. claim-to-evidence map
12. human review checklist
13. final delivery certificate (only after PCE passes)

## Execution Order

### Stage 1 — Build Candidate Trace
先完成：
- mandate
- sources
- retrieval steps
- candidate universe

### Stage 2 — Hard Filter + ER/BRB
对候选池执行：
- hard filters
- exclusion logging
- ER/BRB hard-filter rule scoring

### Stage 3 — DD / Calculations / Risk Trace
对 retained candidates 形成：
- DD evidence rows
- calculation sheet
- risk matrix
- claim-to-evidence map
- ER/BRB post-DD ranking support

### Stage 4 — PCE Check Readiness
逐项检查：
- evidence completeness
- source quality
- calculation replayability
- uncertainty labeling
- human review requirement

### Stage 5 — Final Delivery Gate
只有在 `final_delivery_certificate.md` 可以签发时，才允许输出：
- final report
- case study

## Claim Discipline

- Any material claim must have at least one `source_id`.
- Any financial number in final delivery must appear in `dd_evidence_table.csv` or `financial_calculation_sheet.csv`.
- Any calculation-based claim must be marked `calculation_required = Yes`.
- Any calculation-based claim must not be Certified until `calculation_replayed = Yes`.
- Any high-risk item must trigger `human_review_required = Yes`.
- Unsupported claims must be marked `Insufficient Evidence` or `Rejected`.
- Ambiguous claims must carry `uncertainty_label`.
- Hypothesis must be labeled as hypothesis and cannot be written as fact.

## ER/BRB Integration Rule

ER/BRB 在本项目中不应作为独立 demo 存在，而应融合到主 agent 的两个阶段：

1. **Hard Filter 阶段**
   - 记录规则命中情况
   - 记录 rule rationale
   - 记录 exclusion / retain decision

2. **DD 后排序阶段**
   - 记录 ER/BRB reranking inputs
   - 记录 evidence-backed score adjustments
   - 记录 uncertainty / human review dependencies

任何 ER/BRB 分数都应能够被追溯到：
- rule identifier
- evidence row
- reviewer note（如有）
