"""Trivial: the summary label reads "Average per day"."""


def test_label_is_renamed(run):
    run("add", "30.00", "food", "--date", "2026-03-01")
    _, out = run("summary", "2026-03")
    assert "Average per day" in out
    assert "Daily average" not in out
