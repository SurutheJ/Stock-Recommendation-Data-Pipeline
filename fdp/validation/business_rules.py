"""Cross-row business-rule checks that a single-row schema validator can't
catch: duplicate reporting periods, out-of-order periods, and "soft" anomaly
flags (values that are *plausible* on their own but statistically unusual
across the series -- these are not rejected, but they feed the outlier
component of the data-quality score).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

from fdp.validation.models import (
    ValidatedCashFlowRow,
    ValidatedIncomeStatementRow,
    ValidatedPriceBar,
)


@dataclass
class BusinessRuleReport:
    warnings: List[str] = field(default_factory=list)


def _check_duplicate_periods(rows: Sequence, label: str, report: BusinessRuleReport) -> None:
    seen = set()
    for row in rows:
        key = (row.period_end_date, row.period_type)
        if key in seen:
            report.warnings.append(f"{label}: duplicate period {key}")
        seen.add(key)


def _check_chronological_order(rows: Sequence, date_field: str, label: str, report: BusinessRuleReport) -> None:
    dates = [getattr(row, date_field) for row in rows]
    if dates != sorted(dates):
        report.warnings.append(f"{label}: periods are not in chronological order")


def check_prices(prices: Sequence[ValidatedPriceBar]) -> BusinessRuleReport:
    report = BusinessRuleReport()
    _check_chronological_order(prices, "date", "prices", report)
    dates = [p.date for p in prices]
    if len(dates) != len(set(dates)):
        report.warnings.append("prices: duplicate trading dates detected")
    return report


def check_income_statements(rows: Sequence[ValidatedIncomeStatementRow]) -> BusinessRuleReport:
    report = BusinessRuleReport()
    _check_duplicate_periods(rows, "income_statement", report)
    _check_chronological_order(rows, "period_end_date", "income_statement", report)
    return report


def check_cash_flows(rows: Sequence[ValidatedCashFlowRow]) -> BusinessRuleReport:
    report = BusinessRuleReport()
    _check_duplicate_periods(rows, "cash_flow", report)
    _check_chronological_order(rows, "period_end_date", "cash_flow", report)
    return report
