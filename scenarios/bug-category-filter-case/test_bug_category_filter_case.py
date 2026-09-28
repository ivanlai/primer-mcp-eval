"""Bug C: the list --category filter must ignore case and spacing like the rest of the app."""

import pytest


@pytest.mark.parametrize("given", ["Groceries", "GROCERIES", "  groceries "])
def test_category_filter_ignores_case(run, given):
    run("add", "12.50", "groceries", "--date", "2026-03-01")
    run("add", "3.00", "travel", "--date", "2026-03-02")

    code, out = run("list", "--category", given)
    assert code == 0
    assert "1 expense(s), total 12.50" in out
