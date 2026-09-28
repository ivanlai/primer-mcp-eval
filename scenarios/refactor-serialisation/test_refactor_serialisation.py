"""Refactor: JSON conversion lives in storage, not on Expense; data files still load."""

import json

from expenses.models import Expense


def test_expense_has_no_file_format_methods():
    assert not hasattr(Expense, "to_dict")
    assert not hasattr(Expense, "from_dict")


def test_existing_data_files_still_load(run, tmp_path):
    data = {
        "next_id": 3,
        "expenses": [
            {"id": 1, "date": "2026-03-01", "amount_pence": 1250, "category": "food", "note": "x"},
            {"id": 2, "date": "2026-03-02", "amount_pence": 300, "category": "travel", "note": ""},
        ],
    }
    (tmp_path / "data.json").write_text(json.dumps(data))
    code, out = run("list")
    assert code == 0 and "2 expense(s), total 15.50" in out and "(x)" in out
    assert "Added #3" in run("add", "1.00", "food", "--date", "2026-03-03")[1]
    assert "3 expense(s), total 16.50" in run("list")[1]
