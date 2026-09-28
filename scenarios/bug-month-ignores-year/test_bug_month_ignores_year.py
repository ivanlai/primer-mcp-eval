"""Bug A: month filtering must match the year as well as the month."""


def test_summary_excludes_same_month_of_other_years(run):
    run("add", "10", "food", "--date", "2025-03-10")
    run("add", "20", "food", "--date", "2026-03-10")
    run("add", "40", "food", "--date", "2027-03-10")

    code, out = run("summary", "2026-03")
    assert code == 0
    assert "20.00 (1 expenses)" in out


def test_list_month_excludes_same_month_of_other_years(run):
    run("add", "10", "food", "--date", "2025-03-10")
    run("add", "20", "food", "--date", "2026-03-10")

    code, out = run("list", "--month", "2026-03")
    assert code == 0
    assert "1 expense(s), total 20.00" in out
