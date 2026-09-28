"""JSON file storage for expenses."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from expenses.models import Expense

DEFAULT_PATH = Path.home() / ".expenses.json"
ENV_VAR = "EXPENSES_FILE"


class StorageError(Exception):
    """Raised when the data file exists but cannot be read."""


def default_path() -> Path:
    override = os.environ.get(ENV_VAR)
    return Path(override) if override else DEFAULT_PATH


class ExpenseStore:
    """All expenses in one JSON file, loaded on creation and saved on change."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._next_id = 1
        self._expenses: list[Expense] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._expenses = [Expense.from_dict(item) for item in data["expenses"]]
            self._next_id = int(data["next_id"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise StorageError(f"cannot read {self.path}: {exc}") from exc

    def _save(self) -> None:
        data = {
            "next_id": self._next_id,
            "expenses": [e.to_dict() for e in self._expenses],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def add(self, when: date, amount_pence: int, category: str, note: str = "") -> Expense:
        expense = Expense(
            id=self._next_id,
            date=when,
            amount_pence=amount_pence,
            category=category,
            note=note,
        )
        self._expenses.append(expense)
        self._next_id += 1
        self._save()
        return expense

    def all(self) -> list[Expense]:
        """Every expense, oldest first (ties broken by id)."""
        return sorted(self._expenses, key=lambda e: (e.date, e.id))

    def categories(self) -> list[str]:
        return sorted({e.category for e in self._expenses})
