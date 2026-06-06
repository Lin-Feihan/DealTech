from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _fmt_money(value: Any) -> str:
    num = _num(value)
    if num is None:
        return "未确认"
    yi = num / 100_000_000
    if yi >= 1:
        return f"HK${yi:,.2f}亿"
    wan = num / 10_000
    return f"HK${wan:,.0f}万"


def _fmt_ratio(value: Any) -> str:
    num = _num(value)
    if num is None:
        return "未确认"
    return f"{num:.2f}x"


def _fmt_score(value: Any) -> str:
    num = _num(value)
    if num is None:
        return "未评分"
    return f"{num:.2f}"


def _safe_text(value: Any, fallback: str = "待补充") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _recommendation_label(value: str) -> str:
    return {
        "strong": "优先推进",
        "moderate": "可继续推进",
        "watchlist": "观察名单",
        "exclude": "剔除",
    }.get(str(value or "").strip(), str(value or "未知"))


def _sort_candidates(candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[float, float, float]:
        score = _num(row.get("weighted_total_score")) or -1.0
        value_score = _num(row.get("value_creation_score")) or -1.0
        feasibility = _num(row.get("transaction_feasibility_score")) or -1.0
        return (score, value_score, feasibility)

    return sorted(candidate_rows, key=sort_key, reverse=True)


def build_integrated_report_markdown(
    *,
    screening_rows: list[dict[str, Any]],
    candidate_dd_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    report_date: str | None = None,
    top_n: int = 5,
) -> str:
    report_date = report_date or datetime.now(timezone.utc).date().isoformat()
    screening_map = {str(row.get('stock_code') or ''): row for row in screening_rows}
    ranked = _sort_candidates([r for r in candidate_dd_rows if str(r.get('recommendation_level') or '') != 'exclude'])
    top_candidates = ranked[:top_n]
    pass_count = sum(1 for r in screening_rows if str(r.get('screening_status') or '') == 'pass')
    watch_count = sum(1 for r in screening_rows if str(r.get('screening_status') or '') == 'watchlist')
    exclude_count = sum(1 for r in screening_rows if str(r.get('screening_status') or '') == 'exclude')

    lines: list[str] = []
    lines.append("# 吨吨健康科技集团港股上市公司重组标的筛选报告")
    lines.append("")
    lines.append(f"- 生成日期：{report_date}")
    lines.append("- 版本：v1（自动生成主报告草稿）")
    lines.append("- 报告定位：当前版本已打通从本地数据表到主报告 Markdown 的自动生成链路；Top 名单与排序仍属于 stage-1 / stage-2 之间的 provisional ranking，需继续用官方披露文件补强。")
    lines.append("")
    lines.append("## 1. 免责条款")
    lines.append("")
    lines.append("本报告基于公开资料、结构化市场数据和当前本地运行结果自动生成，不构成法律、财务、税务或投资建议。")
    lines.append("当前版本已经形成可复跑的本地文件与主报告链路，但部分关键结论仍需回到 HKEX 公告、年报、中报及其他官方披露文件做进一步核验。")
    lines.append("")
    lines.append("## 2. 执行摘要")
    lines.append("")
    lines.append("### 2.1 筛选范围与核心方法")
    lines.append(f"- 当前 screenable HK universe：**{len(screening_rows)}** 家")
    lines.append(f"- 初筛结果：pass **{pass_count}** / watchlist **{watch_count}** / exclude **{exclude_count}**")
    lines.append(f"- 候选 DD scaffold：**{len(candidate_dd_rows)}** 家")
    lines.append(f"- 证据表记录：**{len(evidence_rows)}** 条")
    lines.append("- 方法：先做港股可筛 universe 构建，再做机械性低估值 / 小市值 / 流动性初筛，然后生成 provisional DD scaffold、排序和主报告。")
    lines.append("")
    lines.append("### 2.2 当前 Top 候选名单（provisional）")
    lines.append("")
    lines.append("| 排名 | 代码 | 公司 | 当前建议 | provisional score | 一句话协同/平台角度 | 值得推进的一句话理由 |")
    lines.append("| --- | --- | --- | --- | ---: | --- | --- |")
    for idx, row in enumerate(top_candidates, 1):
        screening = screening_map.get(str(row.get('stock_code') or ''), {})
        lines.append(
            f"| {idx} | {row.get('stock_code','')} | {row.get('company_name','')} | {_recommendation_label(str(row.get('recommendation_level') or ''))} | {_fmt_score(row.get('weighted_total_score'))} | {_safe_text(row.get('platform_redefinition_thesis'))} | {_safe_text(screening.get('screening_reason'))} |"
        )
    lines.append("")
    lines.append("### 2.3 当前优先推进顺序判断")
    lines.append("- 当前排序是**可继续推进名单**，不是最终投资结论。")
    lines.append("- 现阶段优先级主要反映：低估值/小市值特征、交易成本可控性、初步平台承载可能性。")
    lines.append("- 现阶段尚未完成：控制权路径验证、审计/诉讼/监管深挖、公告级证据闭环、商业 thesis 定稿。")
    lines.append("")
    lines.append("## 3. 客户概况与重组诉求")
    lines.append("")
    lines.append("吨吨健康科技集团的目标不是被动借道上市，而是寻找一个可承载健康饮水 / 健康生活方式资产注入、品牌升级、渠道扩展和后续融资整合的港股平台。")
    lines.append("当前筛选逻辑围绕以下原则展开：")
    lines.append("- 尽量低估值、低成本切入；")
    lines.append("- 控制权路径尽量清晰；")
    lines.append("- 监管与交易难点可管理；")
    lines.append("- 能承接健康消费 / 生活方式 / 渠道场景的重塑叙事。")
    lines.append("")
    lines.append("## 4. 港股重组监管与市场环境")
    lines.append("")
    lines.append("- **Rule 14.06B / 14.06E** 相关边界决定了报告不能只讲‘壳价值’，而必须兼顾业务连续性、资产注入叙事和监管可接受性。")
    lines.append("- 港股长期存在低估值、小市值、流动性分层明显的特点，为低成本切入提供了筛选空间。")
    lines.append("- 但低估值本身不是充分条件；若控制权、审计、资本结构或监管问题无法闭合，排序应当下降。")
    lines.append("")
    lines.append("## 5. 筛选方法与三层漏斗")
    lines.append("")
    lines.append("### 第一层：价值过滤")
    lines.append("- 小市值")
    lines.append("- 低 P/B")
    lines.append("- 结构化流动性字段可用")
    lines.append("")
    lines.append("### 第二层：交易与风险过滤")
    lines.append("- 剔除明显不属于普通上市公司平台的证券类型（如 SPAC-Z、杠杆/反向产品、票据/结构化产品、特殊柜台等）")
    lines.append("- 优先保留能进入后续控制权路径/公告核验的普通港股公司")
    lines.append("")
    lines.append("### 第三层：平台与协同过滤")
    lines.append("- 基于行业标签和可承载性做 provisional platform angle")
    lines.append("- 先形成 shortlist，再进入正式 DD / 商业 thesis / integrated report 深化")
    lines.append("")
    lines.append("## 6. 候选标的逐家分析")
    lines.append("")
    for idx, row in enumerate(top_candidates, 1):
        screening = screening_map.get(str(row.get('stock_code') or ''), {})
        lines.append(f"### {idx}. {row.get('company_name','')}（{row.get('stock_code','')}）")
        lines.append("")
        lines.append("#### 6.1 基本信息与事实快照")
        lines.append(f"- 市值：{_fmt_money(screening.get('market_cap_hkd'))}")
        lines.append(f"- P/B：{_fmt_ratio(screening.get('pb_ratio'))}")
        lines.append(f"- 板块：{_safe_text(screening.get('board'), 'unknown')}")
        lines.append(f"- 初筛状态：{_safe_text(screening.get('screening_status'))}")
        lines.append(f"- 业务摘要：{_safe_text(row.get('business_summary'))}")
        lines.append("")
        lines.append("#### 6.2 股权结构与控制路径")
        lines.append(f"- 当前控制权路径判断：{_safe_text(row.get('control_path_feasibility'), 'unknown')}")
        lines.append("- 备注：当前版本尚未自动抽取控股股东、持股比例和潜在出售路径，需进入公告/年报核验。 ")
        lines.append("")
        lines.append("#### 6.3 财务与估值快照")
        lines.append(f"- 当前 mechanical distress signal：{_safe_text(row.get('distress_signal'))}")
        lines.append(f"- provisional value creation score：{_fmt_score(row.get('value_creation_score'))}")
        lines.append(f"- provisional transaction feasibility score：{_fmt_score(row.get('transaction_feasibility_score'))}")
        lines.append("")
        lines.append("#### 6.4 关键约束 / 风险 / deal killers")
        lines.append(f"- 核心风险：{_safe_text(row.get('key_risks'))}")
        lines.append(f"- thesis breakers：{_safe_text(row.get('thesis_breakers'))}")
        lines.append("")
        lines.append("#### 6.5 业务与场景协同")
        lines.append(f"- 业务协同：{_safe_text(row.get('synergy_business'))}")
        lines.append(f"- 平台重定义 thesis：{_safe_text(row.get('platform_redefinition_thesis'))}")
        lines.append("")
        lines.append("#### 6.6 情景推演")
        lines.append(f"- Base：{_safe_text(row.get('scenario_base_case'))}")
        lines.append(f"- Upside：{_safe_text(row.get('scenario_upside_case'))}")
        lines.append(f"- Blue-Sky：{_safe_text(row.get('scenario_blue_sky_case'))}")
        lines.append("")
        lines.append("#### 6.7 当前结论与下一步")
        lines.append(f"- 当前建议：{_recommendation_label(str(row.get('recommendation_level') or ''))}")
        lines.append(f"- provisional total score：{_fmt_score(row.get('weighted_total_score'))}")
        lines.append(f"- 下一步 DD：{_safe_text(row.get('next_step'))}")
        lines.append("")
    lines.append("## 7. 候选标的横向比较")
    lines.append("")
    lines.append("| 代码 | 公司 | 市值 | P/B | synergy | value creation | feasibility | risk control | total | 当前建议 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in top_candidates:
        screening = screening_map.get(str(row.get('stock_code') or ''), {})
        lines.append(
            f"| {row.get('stock_code','')} | {row.get('company_name','')} | {_fmt_money(screening.get('market_cap_hkd'))} | {_fmt_ratio(screening.get('pb_ratio'))} | {_fmt_score(row.get('synergy_score'))} | {_fmt_score(row.get('value_creation_score'))} | {_fmt_score(row.get('transaction_feasibility_score'))} | {_fmt_score(row.get('risk_control_score'))} | {_fmt_score(row.get('weighted_total_score'))} | {_recommendation_label(str(row.get('recommendation_level') or ''))} |"
        )
    lines.append("")
    lines.append("## 8. 最终建议与推进顺序")
    lines.append("")
    if top_candidates:
        lines.append(f"- **第一优先**：{top_candidates[0].get('company_name','')}（{top_candidates[0].get('stock_code','')}）—— 当前只代表 stage-1 / stage-2 之间的 provisional first look，不代表最终交易建议。")
    if len(top_candidates) > 1:
        lines.append(f"- **第二优先 / fallback**：{top_candidates[1].get('company_name','')}（{top_candidates[1].get('stock_code','')}）")
    if len(top_candidates) > 2:
        watch_names = ", ".join(
            f"{r.get('company_name', '')}（{r.get('stock_code', '')}）" for r in top_candidates[2:5]
        )
        lines.append(f"- **观察位**：{watch_names}")
    lines.append("- 排序可能变化的关键触发条件：控制权路径不清、审计/监管/诉讼问题暴露、主营业务连续性弱于预期、或无法形成‘业务扩展型收购’监管叙事。")
    lines.append("")
    lines.append("## 9. 待核验事项与下一步工作包")
    lines.append("")
    lines.append("1. 对 Top 名单逐家回到 HKEX 公告、年报、中报和公司披露，补 business / audit / litigation / regulatory / shareholder / control-path 证据。")
    lines.append("2. 把 provisional ranking 升级为 DD-backed ranking，并更新 `candidate_dd_table.csv` 的实质字段。")
    lines.append("3. 将 `source_evidence_table.csv` 从结构化基础证据扩展到公司级 claim evidence，尤其是控制权、审计、交易结构和 thesis breakers。")
    lines.append("4. 在主报告中把当前 provisional Top 名单升级为真正的 Top 3–5 推荐名单，并给出接触顺序和交易结构建议。")
    lines.append("")
    lines.append("## 10. 当前版本说明")
    lines.append("")
    lines.append("- 当前报告已满足‘生成新的本地文件 + 主报告 Markdown’这条链路，但仍不是项目终版。")
    lines.append("- 当前报告的排名和推荐级别主要用于下一步 DD 排兵布阵，而不是替代最终的并购顾问判断。")
    lines.append("- 当前报告可作为后续 run package / 最终报告迭代的基础版本。")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_integrated_report(
    report_path: Path,
    *,
    screening_rows: list[dict[str, Any]],
    candidate_dd_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    report_date: str | None = None,
    top_n: int = 5,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        build_integrated_report_markdown(
            screening_rows=screening_rows,
            candidate_dd_rows=candidate_dd_rows,
            evidence_rows=evidence_rows,
            report_date=report_date,
            top_n=top_n,
        ),
        encoding='utf-8',
    )
