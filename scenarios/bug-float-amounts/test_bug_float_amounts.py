"""Bug B: amounts must be stored exactly as entered."""

import pytest

AMOUNTS = ["0.29", "0.57", "1.15", "4.35", "19.99", "1234.56"]


@pytest.mark.parametrize("amount", AMOUNTS)
def test_amount_is_stored_exactly(run, amount):
    code, out = run("add", amount, "misc", "--date", "2026-03-01")
    assert code == 0
    assert f"Added #1: {amount} misc" in out

    _, out = run("list")
    assert f"total {amount}" in out
