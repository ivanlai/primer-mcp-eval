"""Feature: edit and delete expenses."""


def seed(run):
    run("add", "12.50", "food", "--date", "2026-03-01", "--note", "lunch")
    run("add", "3.00", "travel", "--date", "2026-03-02")


def test_delete_removes_the_expense(run):
    seed(run)
    assert run("delete", "1")[0] == 0
    _, out = run("list")
    assert "1 expense(s), total 3.00" in out
    assert "lunch" not in out


def test_deleted_ids_are_not_reused(run):
    seed(run)
    run("delete", "2")
    _, out = run("add", "5.00", "misc", "--date", "2026-03-03")
    assert "Added #3" in out


def test_edit_changes_only_the_given_fields(run):
    seed(run)
    assert run("edit", "1", "--amount", "20.00")[0] == 0
    _, out = run("list")
    assert "total 23.00" in out
    assert "food" in out and "(lunch)" in out and "2026-03-01" in out


def test_edit_category_note_and_date(run):
    seed(run)
    code, _ = run(
        "edit", "1", "--category", "eating out", "--note", "dinner", "--date", "2026-04-05"
    )
    assert code == 0
    _, out = run("list", "--month", "2026-04")
    assert "1 expense(s), total 12.50" in out
    assert "eating out" in out and "(dinner)" in out


def test_unknown_id_is_an_error(run):
    seed(run)
    assert run("delete", "99")[0] != 0
    assert run("edit", "99", "--amount", "1.00")[0] != 0
    _, out = run("list")
    assert "2 expense(s), total 15.50" in out
