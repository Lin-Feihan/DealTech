# PCE Case Result — Shell Company Screening

Case: `case_001_tonton_shell_company_screening`

Overall status: **Certified with Caveat**

|claim_id|claim_text|source_id|evidence_id|PCE_status|reason|human_review_required|
|---|---|---|---|---|---|---|
|CLM-SHELL-001|TonTon/Tuntun shell-screening source inventory and trace package are present and usable as a certified trace base.|SRC-SHELL-001|EVI-SHELL-001|Certified with Caveat|metadata-level / trace artifact evidence requires caveat or review; human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SHELL-002|DD evidence table supports case-level shell company diligence review with caveats.|SRC-SHELL-002|EVI-SHELL-002|Certified with Caveat|human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SHELL-003|Migrated ER/BRB and PCE artifacts can be used only as caveated certification artifacts, not standalone primary evidence.|SRC-SHELL-003|EVI-SHELL-003|Needs Human Review|source is not PCE eligible; imported artifact cannot serve as primary evidence by itself; human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SHELL-004|Final delivery can be issued only with visible caveats and human-review flags preserved.|SRC-SHELL-004|EVI-SHELL-004|Needs Human Review|source is not PCE eligible; imported artifact cannot serve as primary evidence by itself; human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-CALC-00008|中星集团控股: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-CALC-00012|亚洲果业: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-CALC-00013|渝太地产: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-CALC-00014|谊砾控股: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-CALC-00015|REGAL INT'L: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-CALC-00031|新兴光学: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-CALC-00103|嬴集团: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-CALC-00130|同得仕（集团）: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-CALC-00142|稻香控股: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-CALC-00185|CEC INT'L HOLD: weighted_total_score = 6.37|FINANCIAL_CALCULATION_SHEET||Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-EV-00001|CEC INT'L HOLD: business_summary = Mixed operating platform. Subsidiaries are principally engaged in (i) retail of food and beverage, household and personal care products, (ii) design/development/manufacture/sale of coils, ferrite powder and other electronic components, and (iii) investment property holding.|annual_report|EV-00231|Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|
|CLM-EV-00002|CEC INT'L HOLD: controlling_shareholder = Concentrated control path. Annual report substantial-shareholder section shows Ms. Law Ching Yee and Ka Yan China Development (Holding) / Ka Yan China Investments as controlling shareholder entities, with total interests around 70.89% disclosed in the annual report.|annual_report|EV-00232|Certified|Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope=external_final).; Cross-checked against upstream trace tables by PCE.|no|

## Scoped sampled business claims

Sampling rule: Joined supporting_files/trace/claim_to_evidence_map.csv with supporting_files/pce_audit/pce_audit_current_run.csv, filtered to delivery_scope=external_final, then sampled the first 12 rows sorted by claim_id.

Scoped rows available in `external_final`: 87. Sample shown here: 12 rows.

|claim_id|company_name|stage|source_id|evidence_id|delivery_scope|certification_status|human_review_required|
|---|---|---|---|---|---|---|---|
|CLM-CALC-00008|中星集团控股|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-CALC-00012|亚洲果业|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-CALC-00013|渝太地产|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-CALC-00014|谊砾控股|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-CALC-00015|REGAL INT'L|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-CALC-00031|新兴光学|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-CALC-00103|嬴集团|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-CALC-00130|同得仕（集团）|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-CALC-00142|稻香控股|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-CALC-00185|CEC INT'L HOLD|financial_calculation|FINANCIAL_CALCULATION_SHEET||external_final|Certified|No|
|CLM-EV-00001|CEC INT'L HOLD|dd_evidence|annual_report|EV-00231|external_final|Certified|No|
|CLM-EV-00002|CEC INT'L HOLD|dd_evidence|annual_report|EV-00232|external_final|Certified|No|
