from datetime import date

import pytest

from expenses.models import (
    Expense,
    ValidationError,
    format_amount,
    normalise_category,
    parse_amount,
    parse_date,
    parse_month,
)


@pytest.mark.parametrize(
    ("text", "pence"),
    [("12.50", 1250), ("3", 300), ("0.99", 99), (" 7.1 ", 710), ("1000.00", 100000)],
)
def test_parse_amount(text, pence):
    assert parse_amount(text) == pence


@pytest.mark.parametrize("text", ["", "abc", "0", "-5", "1.234", "nan", "inf"])
def test_parse_amount_rejects_invalid(text):
    with pytest.raises(ValidationError):
        parse_amount(text)


@pytest.mark.parametrize(
    ("pence", "text"),
    [(1250, "12.50"), (5, "0.05"), (0, "0.00"), (100000, "1000.00"), (-250, "-2.50")],
)
def test_format_amount(pence, text):
    assert format_amount(pence) == text


def test_parse_date():
    assert parse_date("2026-03-01") == date(2026, 3, 1)


@pytest.mark.parametrize("text", ["2026-13-01", "01/03/2026", "yesterday"])
def test_parse_date_rejects_invalid(text):
    with pytest.raises(ValidationError):
        parse_date(text)


def test_parse_month():
    assert parse_month("2026-03") == (2026, 3)


@pytest.mark.parametrize(
    "text", ["2026-00", "2026-13", "26-03", "2026/03", "2026-03-01"]
)
def test_parse_month_rejects_invalid(text):
    with pytest.raises(ValidationError):
        parse_month(text)


def test_normalise_category():
    assert normalise_category("  Eating   Out ") == "eating out"


def test_normalise_category_rejects_blank():
    with pytest.raises(ValidationError):
        normalise_category("   ")


def test_expense_round_trips_through_dict():
    expense = Expense(
        id=3, date=date(2026, 3, 1), amount_pence=1250, category="food", note="lunch"
    )
    assert Expense.from_dict(expense.to_dict()) == expense
