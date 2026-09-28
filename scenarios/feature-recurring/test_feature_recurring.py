"""Feature: monthly recurring expenses."""


def seed(run):
    assert run("recurring", "add", "950.00", "rent", "--day", "1")[0] == 0
    assert run("recurring", "add", "12.00", "phone", "--day", "31", "--note", "mobile")[0] == 0


def test_recurring_list(run):
    seed(run)
    code, out = run("recurring", "list")
    assert code == 0
    assert "rent" in out and "950.00" in out
    assert "phone" in out and "12.00" in out


def test_apply_adds_the_month_with_short_month_days_clamped(run):
    seed(run)
    assert run("recurring", "apply", "2026-02")[0] == 0
    _, out = run("list", "--month", "2026-02")
    assert "2 expense(s), total 962.00" in out
    assert "2026-02-01" in out and "2026-02-28" in out
    assert "(mobile)" in out


def test_apply_twice_adds_nothing_new(run):
    seed(run)
    run("recurring", "apply", "2026-02")
    run("recurring", "apply", "2026-02")
    _, out = run("list")
    assert "2 expense(s), total 962.00" in out
