"""Feature: monthly budgets per category."""

import json


def category_line(out, category):
    """Every output line naming the category, joined: budgets may be shown inline or apart."""
    lines = [line for line in out.splitlines() if category in line.split()]
    assert lines, out
    return "\n".join(lines)


def test_budget_set_and_list(run):
    assert run("budget", "set", "food", "50.00")[0] == 0
    run("budget", "set", "travel", "100.00")
    code, out = run("budget", "list")
    assert code == 0
    assert "50.00" in category_line(out, "food")
    assert "100.00" in category_line(out, "travel")


def test_budget_set_replaces(run):
    run("budget", "set", "food", "50.00")
    run("budget", "set", "food", "60.00")
    line = category_line(run("budget", "list")[1], "food")
    assert "60.00" in line and "50.00" not in line


def test_summary_shows_left_and_over_budget(run):
    run("budget", "set", "food", "50.00")
    run("budget", "set", "travel", "100.00")
    run("add", "30.00", "food", "--date", "2026-03-01")
    run("add", "25.00", "food", "--date", "2026-03-02")
    run("add", "10.00", "travel", "--date", "2026-03-03")
    run("add", "7.00", "books", "--date", "2026-03-04")

    code, out = run("summary", "2026-03")
    assert code == 0
    food = category_line(out, "food")
    assert "over budget" in food and "50.00" in food
    travel = category_line(out, "travel")
    assert "over budget" not in travel and "90.00" in travel
    assert "over budget" not in category_line(out, "books")


def test_existing_data_files_keep_working(run, tmp_path):
    old = {
        "next_id": 2,
        "expenses": [
            {"id": 1, "date": "2026-03-01", "amount_pence": 1250, "category": "food", "note": ""}
        ],
    }
    (tmp_path / "data.json").write_text(json.dumps(old))
    code, out = run("summary", "2026-03")
    assert code == 0 and "12.50" in out
    assert run("budget", "set", "food", "20.00")[0] == 0
    assert "Added #2" in run("add", "1.00", "food", "--date", "2026-03-02")[1]
