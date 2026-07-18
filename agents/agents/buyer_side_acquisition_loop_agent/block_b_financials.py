from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from typing import Any

from .block_b_models import (
    FinancialDataPoint,
    FinancialIntegrityGap,
    FinancialIntegrityGapType,
    FinancialNormalizationRecord,
    SynergyRecord,
)


def parse_block_b_financial_payload(
    payload: dict[str, Any], *, module_id: str, provider_attempt_id: str
) -> tuple[list[FinancialDataPoint], list[FinancialNormalizationRecord], list[SynergyRecord]]:
    points = [FinancialDataPoint.from_dict(row) for row in payload.get("financial_data_points", [])]
    normalizations = [
        FinancialNormalizationRecord.from_dict(row)
        for row in payload.get("normalization_records", [])
    ]
    synergies = [SynergyRecord.from_dict(row) for row in payload.get("synergy_records", [])]
    for item in [*points, *synergies]:
        if item.owning_module != module_id:
            raise ValueError(f"{item.__class__.__name__} ownership does not match {module_id}")
        if item.provider_attempt_id != provider_attempt_id:
            raise ValueError(f"{item.__class__.__name__} provider attempt lineage is inconsistent")
    normalisation_by_point = defaultdict(list)
    for item in normalizations:
        normalisation_by_point[item.data_point_id].append(item)
    point_ids = {item.data_point_id for item in points}
    if any(item.data_point_id not in point_ids for item in normalizations):
        raise ValueError("Normalization record references an unknown FinancialDataPoint")
    for point in points:
        changed = point.original_value != point.normalized_value
        records = normalisation_by_point[point.data_point_id]
        if changed and not records:
            raise ValueError(
                f"{point.data_point_id} changed during normalization without an explicit record"
            )
        if records and not any(
            row.original_value == point.original_value
            and row.normalized_value == point.normalized_value
            for row in records
        ):
            raise ValueError(f"{point.data_point_id} does not tie to its normalization record")
    return points, normalizations, synergies


def validate_compatible_financial_points(
    points: list[FinancialDataPoint], *, owning_module: str, purpose: str
) -> list[FinancialIntegrityGap]:
    if len(points) < 2:
        return []
    comparisons: list[tuple[FinancialIntegrityGapType, str, set[str]]] = [
        (FinancialIntegrityGapType.UNIT_MISMATCH, "unit", {item.unit for item in points}),
        (FinancialIntegrityGapType.SCALE_MISMATCH, "scale", {item.scale for item in points}),
        (FinancialIntegrityGapType.CURRENCY_MISMATCH, "currency", {item.currency for item in points}),
        (FinancialIntegrityGapType.PERIOD_MISMATCH, "fiscal period", {item.fiscal_period for item in points}),
        (FinancialIntegrityGapType.PERIMETER_MISMATCH, "company perimeter", {item.company_perimeter for item in points}),
        (
            FinancialIntegrityGapType.ACTUAL_FORECAST_MIX,
            "historical/forecast classification",
            {item.period_classification.value for item in points},
        ),
        (
            FinancialIntegrityGapType.REPORTED_ADJUSTED_MIX,
            "reported/adjusted/estimated classification",
            {item.metric_classification.value for item in points},
        ),
    ]
    gaps = []
    for gap_type, label, values in comparisons:
        if len(values) > 1:
            gaps.append(
                FinancialIntegrityGap(
                    gap_id=f"FID-{owning_module}-{gap_type.value}-{len(gaps) + 1:02d}",
                    gap_type=gap_type,
                    owning_module=owning_module,
                    data_point_ids=[item.data_point_id for item in points],
                    description=f"{purpose} would silently mix {label}: {sorted(values)}.",
                    closure_test=(
                        "Provide an explicit, sourced normalization and compare like-for-like "
                        "financial data before calculation."
                    ),
                )
            )
    return gaps


def validate_no_missing_financial_value(row: dict[str, Any]) -> None:
    for name in ("value", "original_value", "normalized_value"):
        if row.get(name) in (None, ""):
            raise ValueError(f"Missing {name} must remain unknown and must never be converted to zero")


def validate_synergy_separation(synergies: list[SynergyRecord]) -> list[str]:
    failures: list[str] = []
    for item in synergies:
        if item.quantified and (
            not item.mechanism.strip()
            or not item.period.strip()
            or not item.source_ids
            or not item.evidence_ids
        ):
            failures.append(item.synergy_id)
        if item.quantified and not (Decimal("0") <= item.probability <= Decimal("1")):
            failures.append(item.synergy_id)
        if item.quantified and not (Decimal("0") <= item.realization_rate <= Decimal("1")):
            failures.append(item.synergy_id)
    return sorted(set(failures))


def supersede_financial_points(
    current: list[FinancialDataPoint], replacements: list[FinancialDataPoint]
) -> list[FinancialDataPoint]:
    """Return an append-only ledger; latest metric versions are selected elsewhere."""

    existing_ids = {item.data_point_id for item in current}
    if any(item.data_point_id in existing_ids for item in replacements):
        raise ValueError("FinancialDataPoint IDs are append-only")
    return [*current, *replacements]


def latest_financial_points(points: list[FinancialDataPoint]) -> list[FinancialDataPoint]:
    by_key: dict[tuple[str, str, str, str], FinancialDataPoint] = {}
    for item in points:
        key = (item.owning_module, item.metric, item.fiscal_period, item.scenario)
        if key not in by_key or item.version > by_key[key].version:
            by_key[key] = item
    return list(by_key.values())
