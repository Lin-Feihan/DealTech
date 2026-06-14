# AGENT_COMPLETION_GAP_REPORT

## 1. 当前项目统一逻辑：四个 agent 共享 ER/BRB + PCE

不同 M&A 业务场景对应不同业务 agent。每个 agent 走自己的业务流，但成熟 case 共享：ER/BRB 业务筛查、PCE claim-level verification、以及 final delivery 只交付通过证据验证的内容。

## 2. Shell 为什么是 gold-standard template

Shell Company Screening Agent 的 TonTon case 已经具备完整 supporting files、硬筛、DD 证据、risk matrix、calculation sheet、ER/BRB、PCE、scoped claim audit、final delivery certificate，因此适合作为统一模板。

## 3. SPAC before vs after

Before：Soren case 主要是 imported artifact overlay，只有少量 evidence / claim。

After：新增 `supporting_files/`，包含 candidate universe、hard filter、excluded/retained candidates、DD evidence、risk matrix、calculation sheet、ER/BRB scoring、PCE audit；并补齐 final delivery certificate 与 scoped claim audit。

Status boundary：SPAC has been upgraded to a **partially source-replayed screening structure**, but it is **not yet a fully source-replayed complete case** because Aledade, Cityblock Health, DispatchHealth, and Lyra Health have source-replayed identity/business-description rows, but candidate financials, EBITDA, deal value, SPAC readiness, and Apify-authenticated dataset replay remain incomplete. Retained candidates are retained for further review only; they are not final recommended SPAC targets. SPAC overall status remains Needs Human Review unless all material source replay and calculation replay are completed.

## 4. Acquisition buyer_side before vs after

Before：buyer_side 主要是迁移 narrative，source/evidence mapping 较薄。

After：新增 buyer profile、target profile、transaction context、strategic rationale、integration risk、calculation、ER/BRB、PCE、final delivery certificate、scoped audit，并把 valuation/synergy/EPS/go-no-go 明确挡在认证边界之外。

## 5. Acquisition target_side before vs after

Before：target_side 主要是迁移 narrative，缺少 alternatives / offer-attractiveness / PCE 边界分层。

After：新增 standalone case、strategic alternatives、offer attractiveness matrix、risk matrix、calculation、ER/BRB、PCE、final delivery certificate、scoped audit，并明确 fairness / board recommendation / accept-reject-negotiate 不能认证。

## 6. Remaining limitations

- 未新增 primary evidence 抓取。
- Soren 候选公司身份和财务仍需 source replay。
- DarwinAI revenue、EBITDA、deal value、valuation multiple、fairness opinion 仍是 Unknown。
- imported artifact 仍然只能作 context，不能作 primary evidence。
- Merger Strategy Agent 本次未修改。

## 7. Next steps

1. 回补 SPAC 候选公司原始 source packet 并 replay candidate extraction。
2. 如果需要 valuation/fairness，用 source replay + calculation replay 继续补 Apple/DarwinAI。
3. 把新 schema 接到自动校验器里。
4. 单独任务再处理 Merger Strategy Agent。
