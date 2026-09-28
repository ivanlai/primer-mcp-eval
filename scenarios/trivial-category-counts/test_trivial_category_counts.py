"""Trivial: categories shows how many expenses each has."""


def test_categories_show_counts(run):
    run("add", "1.00", "food", "--date", "2026-03-01")
    run("add", "2.00", "food", "--date", "2026-03-02")
    run("add", "3.00", "travel", "--date", "2026-03-03")
    _, out = run("categories")
    assert "food (2)" in out and "travel (1)" in out
