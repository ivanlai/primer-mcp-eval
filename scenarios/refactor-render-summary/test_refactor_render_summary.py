"""Refactor: summary text is built by reports.render_summary; output unchanged."""

from datetime import date

from expenses import reports
from expenses.models import Expense

SHIPPED = """Summary for 2026-03
Total:          50.50 (3 expenses)
Daily average:  1.63
By category:
  food                  42.50   84%  (2)
  travel                 8.00   16%  (1)
"""


def seed(run):
    run("add", "30.00", "food", "--date", "2026-03-01", "--note", "lunch")
    run("add", "12.50", "food", "--date", "2026-03-10")
    run("add", "8.00", "travel", "--date", "2026-03-15")


def test_render_summary_returns_the_text():
    expenses = [Expense(id=1, date=date(2026, 3, 1), amount_pence=3000, category="food")]
    text = reports.render_summary(reports.month_summary(expenses, 2026, 3))
    assert isinstance(text, str)
    assert "Total:" in text and "30.00" in text and "food" in text


def test_summary_output_is_unchanged(run):
    seed(run)
    assert run("summary", "2026-03")[1] == SHIPPED
    assert run("summary", "2026-04")[1] == "Summary for 2026-04\nNo expenses this month.\n"
