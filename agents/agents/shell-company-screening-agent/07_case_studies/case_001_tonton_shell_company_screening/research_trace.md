# Research Trace

## candidate_universe_table.csv

|universe_id|stock_code|company_name|board|industry|market_cap_hkd|pb_ratio|listing_status|
|---|---|---|---|---|---|---|---|
|UNI-00001|00001.HK|长和|unknown||||unknown|
|UNI-00002|00002.HK|中电控股|unknown||||unknown|
|UNI-00003|00003.HK|香港中华煤气|unknown||||unknown|
|UNI-00004|00004.HK|九龙仓集团|unknown||||unknown|
|UNI-00005|00005.HK|汇丰控股|unknown||||unknown|
|UNI-00006|00006.HK|电能实业|unknown||||unknown|
|UNI-00007|00007.HK|智富资源投资|unknown||||unknown|
|UNI-00008|00008.HK|电讯盈科|unknown||||unknown|
|UNI-00009|00010.HK|恒隆集团|unknown||||unknown|
|UNI-00010|00012.HK|恒基地产|unknown||||unknown|

> Showing first 10 rows from `candidate_universe_table.csv`. Full CSV is preserved under `supporting_files/`.

## hard_filter_table.csv

|filter_record_id|stock_code|company_name|filter_stage|filter_name|filter_result|rationale|source_id|
|---|---|---|---|---|---|---|---|
|HF-00001|00001.HK|长和|hard_filter|Generator initial hard filter bundle|exclude|market cap above v0.1 small-cap threshold|AKSHARE_HK_SNAPSHOT_CACHE|
|HF-00002|00002.HK|中电控股|hard_filter|Generator initial hard filter bundle|exclude|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|AKSHARE_HK_SNAPSHOT_CACHE|
|HF-00003|00003.HK|香港中华煤气|hard_filter|Generator initial hard filter bundle|exclude|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|AKSHARE_HK_SNAPSHOT_CACHE|
|HF-00004|00004.HK|九龙仓集团|hard_filter|Generator initial hard filter bundle|exclude|market cap above v0.1 small-cap threshold|AKSHARE_HK_SNAPSHOT_CACHE|
|HF-00005|00005.HK|汇丰控股|hard_filter|Generator initial hard filter bundle|exclude|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|AKSHARE_HK_SNAPSHOT_CACHE|
|HF-00006|00006.HK|电能实业|hard_filter|Generator initial hard filter bundle|exclude|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|AKSHARE_HK_SNAPSHOT_CACHE|
|HF-00007|00007.HK|智富资源投资|hard_filter|Generator initial hard filter bundle|exclude|turnover unavailable or not above minimum|AKSHARE_HK_SNAPSHOT_CACHE|
|HF-00008|00008.HK|电讯盈科|hard_filter|Generator initial hard filter bundle|exclude|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|AKSHARE_HK_SNAPSHOT_CACHE|
|HF-00009|00010.HK|恒隆集团|hard_filter|Generator initial hard filter bundle|exclude|market cap above v0.1 small-cap threshold|AKSHARE_HK_SNAPSHOT_CACHE|
|HF-00010|00012.HK|恒基地产|hard_filter|Generator initial hard filter bundle|exclude|market cap above v0.1 small-cap threshold|AKSHARE_HK_SNAPSHOT_CACHE|

> Showing first 10 rows from `hard_filter_table.csv`. Full CSV is preserved under `supporting_files/`.

## exclusion_reason_table.csv

|exclusion_id|stock_code|company_name|exclusion_stage|exclusion_reason|severity|source_id|uncertainty_label|
|---|---|---|---|---|---|---|---|
|EX-00001|00001.HK|长和|hard_filter|market cap above v0.1 small-cap threshold|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|
|EX-00002|00002.HK|中电控股|hard_filter|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|
|EX-00003|00003.HK|香港中华煤气|hard_filter|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|
|EX-00004|00004.HK|九龙仓集团|hard_filter|market cap above v0.1 small-cap threshold|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|
|EX-00005|00005.HK|汇丰控股|hard_filter|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|
|EX-00006|00006.HK|电能实业|hard_filter|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|
|EX-00007|00007.HK|智富资源投资|hard_filter|turnover unavailable or not above minimum|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|
|EX-00008|00008.HK|电讯盈科|hard_filter|market cap above v0.1 small-cap threshold; P/B does not satisfy low-valuation threshold or is non-positive|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|
|EX-00009|00010.HK|恒隆集团|hard_filter|market cap above v0.1 small-cap threshold|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|
|EX-00010|00012.HK|恒基地产|hard_filter|market cap above v0.1 small-cap threshold|medium|AKSHARE_HK_SNAPSHOT_CACHE|partial_support|

> Showing first 10 rows from `exclusion_reason_table.csv`. Full CSV is preserved under `supporting_files/`.

## er_brb_scoring_table.csv

|er_brb_id|stage|stock_code|company_name|rule_id|rule_family|score_component|score_value|
|---|---|---|---|---|---|---|---|
|ERBRB-00001|hard_filter|00001.HK|长和|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|
|ERBRB-00002|hard_filter|00002.HK|中电控股|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|
|ERBRB-00003|hard_filter|00003.HK|香港中华煤气|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|
|ERBRB-00004|hard_filter|00004.HK|九龙仓集团|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|
|ERBRB-00005|hard_filter|00005.HK|汇丰控股|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|
|ERBRB-00006|hard_filter|00006.HK|电能实业|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|
|ERBRB-00007|hard_filter|00007.HK|智富资源投资|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|
|ERBRB-00008|hard_filter|00008.HK|电讯盈科|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|
|ERBRB-00009|hard_filter|00010.HK|恒隆集团|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|
|ERBRB-00010|hard_filter|00012.HK|恒基地产|ERHF-GENERATOR-BUNDLE|hard_filter_mechanical_gate|hard_filter_retention_signal|0.0|

> Showing first 10 rows from `er_brb_scoring_table.csv`. Full CSV is preserved under `supporting_files/`.

## risk_matrix.csv

|risk_id|stock_code|company_name|risk_category|risk_flag|risk_description|source_id|severity|
|---|---|---|---|---|---|---|---|
|RISK-00001|00001.HK|长和|suspension|unknown|Generator screening flagged suspension: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|
|RISK-00002|00001.HK|长和|audit|unknown|Generator screening flagged audit: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|
|RISK-00003|00001.HK|长和|major_risk|unknown|Generator screening flagged major_risk: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|
|RISK-00004|00002.HK|中电控股|suspension|unknown|Generator screening flagged suspension: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|
|RISK-00005|00002.HK|中电控股|audit|unknown|Generator screening flagged audit: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|
|RISK-00006|00002.HK|中电控股|major_risk|unknown|Generator screening flagged major_risk: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|
|RISK-00007|00003.HK|香港中华煤气|suspension|unknown|Generator screening flagged suspension: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|
|RISK-00008|00003.HK|香港中华煤气|audit|unknown|Generator screening flagged audit: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|
|RISK-00009|00003.HK|香港中华煤气|major_risk|unknown|Generator screening flagged major_risk: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|
|RISK-00010|00004.HK|九龙仓集团|suspension|unknown|Generator screening flagged suspension: unknown.|AKSHARE_HK_SNAPSHOT_CACHE|medium|

> Showing first 10 rows from `risk_matrix.csv`. Full CSV is preserved under `supporting_files/`.

## financial_calculation_sheet.csv

|calc_id|stock_code|company_name|metric_name|input_1|input_2|formula_or_logic|output_value|
|---|---|---|---|---|---|---|---|
|CALC-00001|00018.HK|东方传媒集团|weighted_total_score|synergy_score=5.0; value_creation_score=7.8; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|6.01|
|CALC-00002|00021.HK|大中华控股|weighted_total_score|synergy_score=5.0; value_creation_score=8.3; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|6.17|
|CALC-00003|00022.HK|茂盛控股|weighted_total_score|synergy_score=5.0; value_creation_score=8.3; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|6.17|
|CALC-00004|00031.HK|航天控股|weighted_total_score|synergy_score=5.0; value_creation_score=7.5; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|5.92|
|CALC-00005|00040.HK|金山科技工业|weighted_total_score|synergy_score=5.0; value_creation_score=7.0; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|5.77|
|CALC-00006|00050.HK|香港小轮（集团）|weighted_total_score|synergy_score=5.0; value_creation_score=7.5; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|5.92|
|CALC-00007|00052.HK|大快活集团|weighted_total_score|synergy_score=5.0; value_creation_score=7.0; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|5.77|
|CALC-00008|00055.HK|中星集团控股|weighted_total_score|synergy_score=5.0; value_creation_score=9.0; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|6.37|
|CALC-00009|00057.HK|震雄集团|weighted_total_score|synergy_score=5.0; value_creation_score=6.8; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|5.71|
|CALC-00010|00063.HK|中亚烯谷集团|weighted_total_score|synergy_score=5.0; value_creation_score=7.5; transaction_feasibility_score=6.0; risk_control_score=4.5|weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15|weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15|5.92|

> Showing first 10 rows from `financial_calculation_sheet.csv`. Full CSV is preserved under `supporting_files/`.

## claim_to_evidence_map.csv

|claim_id|claim_text|company_name|stage|source_id|evidence_id|calc_id|risk_id|
|---|---|---|---|---|---|---|---|
|CLM-EV-00001|CEC INT'L HOLD: business_summary = Mixed operating platform. Subsidiaries are principally engaged in (i) retail of food and beverage, househ|CEC INT'L HOLD|dd_evidence|annual_report|EV-00231|||
|CLM-EV-00002|CEC INT'L HOLD: controlling_shareholder = Concentrated control path. Annual report substantial-shareholder section shows Ms. Law Ching Yee a|CEC INT'L HOLD|dd_evidence|annual_report|EV-00232|||
|CLM-EV-00003|CEC INT'L HOLD: audit_risk = Clean / unqualified audit opinion. PricewaterhouseCoopers stated the FY2025 consolidated financial statements g|CEC INT'L HOLD|dd_evidence|annual_report|EV-00233|||
|CLM-EV-00004|CEC INT'L HOLD: debt_risk = No major litigation/regulatory issue identified in reviewed documents. Earnings quality remains weak: FY2025 rev|CEC INT'L HOLD|dd_evidence|results_announcement|EV-00234|||
|CLM-EV-00005|CEC INT'L HOLD: regulatory_risk = No major litigation/regulatory issue identified in reviewed documents. Earnings quality remains weak: FY20|CEC INT'L HOLD|dd_evidence|results_announcement|EV-00235|||
|CLM-EV-00006|CEC INT'L HOLD: transaction_complexity = High. Annual-report structure review strengthens the messy-restructuring reading: the platform stil|CEC INT'L HOLD|dd_evidence|annual_report|EV-00236|||
|CLM-EV-00007|稻香控股: business_summary = Direct F&B operating platform. The group is principally involved in restaurant and bakery operations, provision of |稻香控股|dd_evidence|annual_report|EV-00245|||
|CLM-EV-00008|稻香控股: controlling_shareholder = Founder / family-trust controlled and operationally family-embedded. Annual report substantial-shareholder s|稻香控股|dd_evidence|annual_report|EV-00246|||
|CLM-EV-00009|稻香控股: audit_risk = Clean / unqualified audit opinion. Ernst & Young stated the FY2025 consolidated financial statements give a true and fair|稻香控股|dd_evidence|annual_report|EV-00247|||
|CLM-EV-00010|稻香控股: debt_risk = No major litigation / regulatory issue identified in the reviewed documents. Operating pressure is visible: FY2025 revenue|稻香控股|dd_evidence|results_announcement|EV-00248|||

> Showing first 10 rows from `claim_to_evidence_map.csv`. Full CSV is preserved under `supporting_files/`.

## human_review_checklist.csv

|review_item_id|company_name|review_topic|trigger_reason|priority|required_reviewer_type|assigned_reviewer_name|status|
|---|---|---|---|---|---|---|---|

## workflow_pce_er_brb_map.csv

|step|workflow_stage|agent_action|er_brb_role|pce_certification_check|output_artifact|
|---|---|---|---|---|---|
|0|Mandate|Capture user objective, market scope and delivery boundary|Not a scoring step; defines rule boundary|Mandate is explicit and final delivery does not exceed scope|mandate_record.md|
|1|Universe Construction|Build HK-listed candidate universe|Not primary decision point|Universe rows trace to permitted sources|candidate_universe_table.csv|
|2|Hard Filter|Apply mechanical and rule-based exclusion/retention filters|HF-level ER/BRB fuses preliminary evidence into pass/exclude/watchlist/DD escalation + confidence|Filter decisions have source, rule, rationale and uncertainty label|hard_filter_table.csv; exclusion_reason_table.csv; er_brb_scoring_table.csv|
|3|Deep Due Diligence|Review control, debt/litigation, compliance, announcements, carrying cost|DD-level ER/BRB aggregates deep evidence and calibrates reranking/recommendation|Material DD risks are reflected in risk matrix, claim map and human review flags|dd_evidence_table.csv; risk_matrix.csv|
|4|Certified Research Trace|Link mandate, source, retrieval, HF, DD, ER/BRB and claims|Both HF-ER/BRB and DD-ER/BRB must be trace-linked|No unsupported material claims or broken evidence chains|claim_to_evidence_map.csv; certified_research_trace_definition.md|
|5|PCE Certification|External gate checks trajectory|Certifies ER/BRB use; does not create new business judgment|Certified / DD issues / revision / escalation / rejected|trajectory_certification_report.md; claim_level_audit.xlsx|
|6|Execution|Release final certified materials|Uses certified DD-ER/BRB-supported recommendation only|Final report only uses certified claims|certified_final_report.md; certified_case_study.md; certified_dd_pack.md|
