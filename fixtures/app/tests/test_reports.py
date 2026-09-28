from datetime import date

from expenses.models import Expense
from expenses.reports import in_category, in_month, month_summary


def make(id_, day, pence, category):
    return Expense(id=id_, date=day, amount_pence=pence, category=category)


EXPENSES = [
    make(1, date(2026, 2, 28), 1000, "food"),
    make(2, date(2026, 3, 1), 3000, "food"),
    make(3, date(2026, 3, 15), 1000, "travel"),
    make(4, date(2026, 3, 31), 2000, "food"),
]


def test_in_month():
    assert [e.id for e in in_month(EXPENSES, 2026, 3)] == [2, 3, 4]


def test_in_category():
    assert [e.id for e in in_category(EXPENSES, "travel")] == [3]


def test_month_summary_totals():
    summary = month_summary(EXPENSES, 2026, 3)
    assert summary.total_pence == 6000
    assert summary.count == 3


def test_month_summary_breakdown_is_largest_first():
    summary = month_summary(EXPENSES, 2026, 3)
    assert [(c.category, c.total_pence, c.count) for c in summary.by_category] == [
        ("food", 5000, 2),
        ("travel", 1000, 1),
    ]
    assert [c.share_percent for c in summary.by_category] == [83, 17]


def test_month_summary_ties_sorted_by_name():
    expenses = [
        make(1, date(2026, 3, 1), 500, "b"),
        make(2, date(2026, 3, 1), 500, "a"),
    ]
    assert [c.category for c in month_summary(expenses, 2026, 3).by_category] == [
        "a",
        "b",
    ]


def test_daily_average_uses_days_in_month():
    assert month_summary(EXPENSES, 2026, 3).daily_average_pence == round(6000 / 31)


def test_empty_month():
    summary = month_summary(EXPENSES, 2026, 4)
    assert (summary.total_pence, summary.count, summary.daily_average_pence) == (
        0,
        0,
        0,
    )
    assert summary.by_category == []
