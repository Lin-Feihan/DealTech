# Case Study Generation Prompt

## Purpose

本 prompt 用于在最终阶段，根据已认证的 trace、PCE 结果与 audit spreadsheet，生成统一格式的 case study。

它不是替代最终报告，而是与最终报告并列的第二份交付物。

## Hard Rule

只有在以下条件满足后，才允许生成 case study：

- Certified Research Trace 已完成
- PCE workflow 已完成必要检查
- PCE Audit Spreadsheet 已有可审阅状态
- `final_delivery_certificate.md` 已具备可签发条件

否则：
- 不得生成看似完整的 case study
- 必须先说明 trace / certification 缺口

## Input Files

生成 case study 时应优先读取：

- `01_case_input/case_input.md`
- `03_sources/source_map.md`
- `certified_research_trace/mandate_record.md`
- `certified_research_trace/source_inventory.csv`
- `certified_research_trace/retrieval_log.csv`
- `certified_research_trace/candidate_universe_table.csv`
- `certified_research_trace/hard_filter_table.csv`
- `certified_research_trace/exclusion_reason_table.csv`
- `certified_research_trace/dd_evidence_table.csv`
- `certified_research_trace/risk_matrix.csv`
- `certified_research_trace/financial_calculation_sheet.csv`
- `certified_research_trace/er_brb_scoring_table.csv`
- `certified_research_trace/claim_to_evidence_map.csv`
- `certified_research_trace/human_review_checklist.csv`
- `certified_research_trace/final_delivery_certificate.md`
- `pce_audit_spreadsheet/pce_audit_spreadsheet_template.csv` or current run spreadsheet

## Required Case Study Structure

Case study 必须按以下顺序组织：

1. Case name
2. Business question
3. User mandate
4. Market scope
5. Initial candidate universe
6. Key data sources
7. Hard filters
8. Companies excluded and why
9. Companies retained and why
10. Deep DD evidence
11. Major risk flags
12. Financial calculations
13. ER/BRB scoring
14. Human review items
15. Final shortlist
16. What the agent did well
17. What still requires human judgment
18. Certified Research Trace

## Writing Discipline

- 不要把 case study 写成营销稿。
- 不要把 hypothesis 写成事实。
- 所有 material claims 尽量回指到 trace file 或 source_id。
- 需明确哪些步骤是 agent 完成的，哪些是人审 / certification gate 完成的。
- 必须体现：最终 shortlist 不是“模型直接给出”，而是“经 trace + PCE + audit 后保留下来的结论”。

## Output Target

建议输出到：

`outputs/case_studies/tuntun_hk_case_study.md`
