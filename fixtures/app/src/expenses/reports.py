"""Filtering and monthly summaries."""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass

from expenses.models import Expense


def in_month(expenses: list[Expense], year: int, month: int) -> list[Expense]:
    return [e for e in expenses if e.date.year == year and e.date.month == month]


def in_category(expenses: list[Expense], category: str) -> list[Expense]:
    return [e for e in expenses if e.category == category]


@dataclass(frozen=True)
class CategoryTotal:
    category: str
    total_pence: int
    count: int
    share_percent: int


@dataclass(frozen=True)
class MonthSummary:
    year: int
    month: int
    total_pence: int
    count: int
    daily_average_pence: int
    by_category: list[CategoryTotal]


def month_summary(expenses: list[Expense], year: int, month: int) -> MonthSummary:
    """Totals for one month, with a per-category breakdown largest first."""
    selected = in_month(expenses, year, month)
    total = sum(e.amount_pence for e in selected)
    days = calendar.monthrange(year, month)[1]

    totals: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    for e in selected:
        totals[e.category] += e.amount_pence
        counts[e.category] += 1

    by_category = [
        CategoryTotal(
            category=cat,
            total_pence=amount,
            count=counts[cat],
            share_percent=round(amount * 100 / total) if total else 0,
        )
        for cat, amount in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return MonthSummary(
        year=year,
        month=month,
        total_pence=total,
        count=len(selected),
        daily_average_pence=round(total / days),
        by_category=by_category,
    )
