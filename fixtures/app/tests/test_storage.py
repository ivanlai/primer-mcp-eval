from datetime import date

import pytest

from expenses.storage import ExpenseStore, StorageError, default_path


def test_new_store_is_empty(tmp_path):
    store = ExpenseStore(tmp_path / "data.json")
    assert store.all() == []
    assert store.categories() == []


def test_add_persists_and_assigns_ids(tmp_path):
    path = tmp_path / "data.json"
    store = ExpenseStore(path)
    first = store.add(date(2026, 3, 2), 500, "food")
    second = store.add(date(2026, 3, 1), 250, "travel", "bus")

    assert (first.id, second.id) == (1, 2)
    reloaded = ExpenseStore(path)
    assert reloaded.all() == [second, first]
    assert reloaded.add(date(2026, 3, 3), 100, "food").id == 3


def test_all_is_sorted_by_date_then_id(tmp_path):
    store = ExpenseStore(tmp_path / "data.json")
    store.add(date(2026, 3, 5), 100, "a")
    store.add(date(2026, 3, 1), 100, "b")
    store.add(date(2026, 3, 5), 100, "c")
    assert [e.category for e in store.all()] == ["b", "a", "c"]


def test_categories_are_unique_and_sorted(tmp_path):
    store = ExpenseStore(tmp_path / "data.json")
    for category in ["travel", "food", "travel", "bills"]:
        store.add(date(2026, 3, 1), 100, category)
    assert store.categories() == ["bills", "food", "travel"]


def test_creates_missing_parent_directory(tmp_path):
    path = tmp_path / "nested" / "data.json"
    ExpenseStore(path).add(date(2026, 3, 1), 100, "food")
    assert path.exists()


def test_corrupt_file_raises_storage_error(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{not json")
    with pytest.raises(StorageError):
        ExpenseStore(path)


def test_default_path_honours_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPENSES_FILE", str(tmp_path / "custom.json"))
    assert default_path() == tmp_path / "custom.json"
