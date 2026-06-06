# Certified Research Trace Definition

## Core Principle

> No certified trace, no final delivery.

## What Certified Research Trace Means in This Case

在吨吨健康科技集团港股上市公司重组标的筛选这个 case 中，Certified Research Trace 指的是：

- agent 如何接收 mandate
- 使用了哪些 sources
- 检索了哪些文件
- 候选池如何形成
- 哪些公司被排除，为什么
- 哪些公司被保留，为什么
- DD 证据是什么
- 风险标记是什么
- 金融计算如何得出
- ER/BRB 规则如何影响筛选和排序
- 哪些结论需要 human review
- 最终为何允许或不允许交付

## File-by-File Definition

### 1. `mandate_record.md`
- **Purpose:** 记录本次 case mandate、约束、范围和目标交付。
- **Required fields:** case_name, business_question, user_mandate, market_scope, run_objective, delivery_boundary.
- **Example rows or placeholders:** 见文件模板中的占位段落。
- **Upstream source file:** `01_case_input/case_input.md`.
- **Downstream use in case study:** 填充 Case name / Business question / User mandate / Market scope.
- **How PCE will check it:** 检查 mandate 是否明确、是否与最终交付范围一致。

### 2. `source_inventory.csv`
- **Purpose:** 列出允许使用的数据源及其优先级。
- **Required fields:** source_id, source_name, source_category, priority_level, official_status, allowed_use, restrictions, default_confidence.
- **Example rows or placeholders:** 模板中包含 HKEXNEWS_OFFICIAL、AKSHARE_HK 等示例。
- **Upstream source file:** `03_sources/source_map.md`.
- **Downstream use in case study:** 填充 Key data sources。
- **How PCE will check it:** 检查高置信结论是否依赖合格 source。

### 3. `retrieval_log.csv`
- **Purpose:** 记录检索动作和取得的证据链路。
- **Required fields:** retrieval_id, retrieval_datetime, stage, company_name, source_id, query_or_document, action_taken, output_file, result_status, notes.
- **Example rows or placeholders:** 模板中给出 placeholder 行。
- **Upstream source file:** generator run steps / manual retrieval logs.
- **Downstream use in case study:** 支撑 Certified Research Trace 章节。
- **How PCE will check it:** 检查证据取得过程是否存在断链。

### 4. `candidate_universe_table.csv`
- **Purpose:** 记录初始 candidate universe。
- **Required fields:** universe_id, stock_code, company_name, board, industry, market_cap_hkd, pb_ratio, listing_status, initial_inclusion_reason, source_id, data_date.
- **Example rows or placeholders:** 模板中给出示例列和 placeholder。
- **Upstream source file:** 原 `initial_screening_table` 思路 + HKEX/AKShare universe。
- **Downstream use in case study:** 填充 Initial candidate universe。
- **How PCE will check it:** 检查 universe 是否可追溯、字段是否足够。

### 5. `hard_filter_table.csv`
- **Purpose:** 记录 hard filters 的逐条判断。
- **Required fields:** filter_record_id, stock_code, company_name, filter_stage, filter_name, filter_result, rationale, source_id, er_brb_rule_id, human_review_required.
- **Example rows or placeholders:** 模板中给出 placeholder 行。
- **Upstream source file:** 原初筛逻辑 + ER/BRB hard filter rules。
- **Downstream use in case study:** 填充 Hard filters / Companies retained and why。
- **How PCE will check it:** 检查 retain / exclude 是否有规则与来源支撑。

### 6. `exclusion_reason_table.csv`
- **Purpose:** 记录被排除公司的原因。
- **Required fields:** exclusion_id, stock_code, company_name, exclusion_stage, exclusion_reason, severity, source_id, uncertainty_label, reviewer_note.
- **Example rows or placeholders:** 模板中给出 placeholder 行。
- **Upstream source file:** `hard_filter_table.csv` / DD 阶段剔除结论。
- **Downstream use in case study:** 填充 Companies excluded and why。
- **How PCE will check it:** 检查排除逻辑是否一致、是否存在 unsupported exclusion。

### 7. `dd_evidence_table.csv`
- **Purpose:** 记录 DD 事实、判断和假说的证据。
- **Required fields:** evidence_id, stock_code, company_name, field_name, field_value, claim_type, source_id, source_title, source_link_or_file, support_level, verification_status, confidence_level, notes.
- **Example rows or placeholders:** 模板中给出 placeholder 行。
- **Upstream source file:** 原 `source_evidence_table.csv` 逻辑 + DD 摘要。
- **Downstream use in case study:** 填充 Deep DD evidence。
- **How PCE will check it:** 检查 material claims 是否至少有一条 source-linked evidence。

### 8. `risk_matrix.csv`
- **Purpose:** 记录 deal / DD / audit / regulatory 风险。
- **Required fields:** risk_id, stock_code, company_name, risk_category, risk_flag, risk_description, source_id, severity, human_review_required, mitigation_or_next_step.
- **Example rows or placeholders:** 模板中给出 placeholder 行。
- **Upstream source file:** DD 结论、公告、年报、人工复核要求。
- **Downstream use in case study:** 填充 Major risk flags / Human review items。
- **How PCE will check it:** 检查 high-risk 是否都触发 human review。

### 9. `financial_calculation_sheet.csv`
- **Purpose:** 记录计算型结论的可重放过程。
- **Required fields:** calc_id, stock_code, company_name, metric_name, input_1, input_2, formula_or_logic, output_value, unit, calculation_required, calculation_replayed, linked_claim_id, notes.
- **Example rows or placeholders:** 模板中给出 placeholder 行。
- **Upstream source file:** 财务快照、排序计算、估值逻辑。
- **Downstream use in case study:** 填充 Financial calculations。
- **How PCE will check it:** 检查 calculation-based claims 是否 replayed。

### 10. `er_brb_scoring_table.csv`
- **Purpose:** 记录 ER/BRB 在 hard filter 与 DD reranking 的使用。
- **Required fields:** er_brb_id, stage, stock_code, company_name, rule_id, score_component, score_value, rationale, source_id, linked_claim_id, uncertainty_label, human_review_required.
- **Example rows or placeholders:** 模板中给出 placeholder 行。
- **Upstream source file:** ER/BRB 规则框架、hard filter table、DD reranking。
- **Downstream use in case study:** 填充 ER/BRB scoring / Final shortlist explanation。
- **How PCE will check it:** 检查 rule score 是否可追溯到 evidence / claim / rationale。

### 11. `claim_to_evidence_map.csv`
- **Purpose:** 把 final report / case study 中的 claim 映射到 evidence、calculation、risk、review 状态。
- **Required fields:** claim_id, claim_text, company_name, stage, source_id, evidence_id, calc_id, risk_id, calculation_required, calculation_replayed, uncertainty_label, human_review_required, certification_status.
- **Example rows or placeholders:** 模板中给出 placeholder 行。
- **Upstream source file:** DD evidence, calculation sheet, risk matrix, draft report claims。
- **Downstream use in case study:** 填充 Certified Research Trace / Human review items / Final shortlist support。
- **How PCE will check it:** 是最关键的 certification mapping 文件之一。

### 12. `human_review_checklist.csv`
- **Purpose:** 记录哪些项目必须由人审确认。
- **Required fields:** review_item_id, company_name, review_topic, trigger_reason, priority, required_reviewer_type, status, linked_claim_id, notes.
- **Example rows or placeholders:** 模板中给出 placeholder 行。
- **Upstream source file:** 原 manual review checklist + risk / uncertainty triggers。
- **Downstream use in case study:** 填充 Human review items。
- **How PCE will check it:** 检查 high-risk / ambiguity 是否真正进入人审。

### 13. `final_delivery_certificate.md`
- **Purpose:** 记录本次交付是否允许签发。
- **Required fields:** certificate_status, case_name, trace_id, certification_scope, blockers, residual_dd_issues, approved_deliverables, reviewer_signoff.
- **Example rows or placeholders:** 见模板。
- **Upstream source file:** 全部 trace + PCE workflow + audit spreadsheet。
- **Downstream use in case study:** 填充 Certified Research Trace / Final shortlist boundary。
- **How PCE will check it:** 没有 certificate，则 final delivery 不成立。
