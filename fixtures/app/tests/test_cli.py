import pytest

from expenses.cli import main


@pytest.fixture
def run(tmp_path, capsys):
    data = tmp_path / "data.json"

    def _run(*args):
        code = main(["--file", str(data), *args])
        out, err = capsys.readouterr()
        return code, out, err

    return _run


def test_add_and_list(run):
    assert (
        run("add", "12.50", "Food", "--date", "2026-03-01", "--note", "lunch")[0] == 0
    )
    assert run("add", "3", "travel", "--date", "2026-03-02")[0] == 0

    code, out, _ = run("list")
    assert code == 0
    assert "#1" in out and "12.50" in out and "food" in out and "(lunch)" in out
    assert "2 expense(s), total 15.50" in out


def test_add_reports_what_was_added(run):
    code, out, _ = run("add", "4.20", "coffee", "--date", "2026-03-01")
    assert code == 0
    assert out.strip() == "Added #1: 4.20 coffee on 2026-03-01"


def test_list_filters_by_month_and_category(run):
    run("add", "1", "food", "--date", "2026-02-28")
    run("add", "2", "food", "--date", "2026-03-01")
    run("add", "3", "travel", "--date", "2026-03-02")

    _, out, _ = run("list", "--month", "2026-03", "--category", "FOOD")
    assert "2.00" in out and "1.00" not in out and "3.00" not in out
    assert "1 expense(s), total 2.00" in out


def test_list_empty(run):
    assert run("list")[1].strip() == "No expenses found."


def test_categories(run):
    run("add", "1", "travel", "--date", "2026-03-01")
    run("add", "1", "food", "--date", "2026-03-01")
    assert run("categories")[1].split() == ["food", "travel"]


def test_summary(run):
    run("add", "30", "food", "--date", "2026-03-01")
    run("add", "10", "travel", "--date", "2026-03-15")

    code, out, _ = run("summary", "2026-03")
    assert code == 0
    assert "Total:          40.00 (2 expenses)" in out
    assert "Daily average:  1.29" in out
    assert "food" in out and "75%" in out


def test_summary_empty_month(run):
    assert "No expenses this month." in run("summary", "2026-04")[1]


def test_invalid_input_is_an_error(run):
    code, _, err = run("add", "-5", "food")
    assert code == 1
    assert "error:" in err


def test_corrupt_file_is_an_error(tmp_path, capsys):
    data = tmp_path / "data.json"
    data.write_text("[]")
    assert main(["--file", str(data), "list"]) == 1
    assert "cannot read" in capsys.readouterr().err
