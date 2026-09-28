"""Feature: CSV export and import."""

import csv
import re

from expenses.cli import main


def test_export_writes_header_and_rows(run, tmp_path):
    run("add", "12.50", "food", "--date", "2026-03-01", "--note", "lunch")
    run("add", "3.00", "travel", "--date", "2026-03-02")
    out_file = tmp_path / "out.csv"

    assert run("export", str(out_file))[0] == 0
    with out_file.open(newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["date", "amount", "category", "note"]
        rows = list(reader)
    assert rows == [
        {"date": "2026-03-01", "amount": "12.50", "category": "food", "note": "lunch"},
        {"date": "2026-03-02", "amount": "3.00", "category": "travel", "note": ""},
    ]


def test_export_then_import_round_trips(run, tmp_path, capsys):
    run("add", "12.50", "food", "--date", "2026-03-01", "--note", "lunch")
    run("add", "7.25", "travel", "--date", "2026-03-02")
    out_file = tmp_path / "out.csv"
    run("export", str(out_file))

    other = str(tmp_path / "other.json")
    assert main(["--file", other, "import", str(out_file)]) == 0
    capsys.readouterr()
    main(["--file", other, "list"])
    listing = capsys.readouterr().out
    assert "2 expense(s), total 19.75" in listing
    assert "(lunch)" in listing


def test_invalid_rows_import_nothing_and_report_lines(run, tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "date,amount,category,note\n"
        "2026-03-01,12.50,food,\n"
        "2026-03-02,abc,food,\n"
        "yesterday,3.00,travel,\n"
        "2026-03-05,7.25,travel,\n"
    )
    code = main(["--file", str(tmp_path / "data.json"), "import", str(bad)])
    captured = capsys.readouterr()
    assert code != 0
    message = captured.out + captured.err
    assert re.search(r"\b3\b", message) and re.search(r"\b4\b", message), message
    assert run("list")[1].strip() == "No expenses found."
