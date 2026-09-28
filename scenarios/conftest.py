import pytest

from expenses.cli import main


@pytest.fixture
def run(tmp_path, capsys):
    """Run the expenses CLI against a fresh data file; return (exit code, stdout)."""
    data = tmp_path / "data.json"

    def _run(*args):
        code = main(["--file", str(data), *args])
        return code, capsys.readouterr().out

    return _run
