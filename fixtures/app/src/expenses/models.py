"""Expense records and the parsing/formatting rules for their fields."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


class ValidationError(ValueError):
    """Raised when user input cannot be turned into a valid expense field."""


@dataclass(frozen=True)
class Expense:
    id: int
    date: date
    amount_pence: int
    category: str
    note: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["date"] = self.date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Expense:
        return cls(
            id=int(data["id"]),
            date=date.fromisoformat(data["date"]),
            amount_pence=int(data["amount_pence"]),
            category=data["category"],
            note=data.get("note", ""),
        )


def parse_amount(text: str) -> int:
    """Parse a user-entered amount such as "12.50" into whole pence."""
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise ValidationError(f"not a valid amount: {text!r}") from None
    if not value.is_finite():
        raise ValidationError(f"not a valid amount: {text!r}")
    if value <= 0:
        raise ValidationError("amount must be greater than zero")
    if value.as_tuple().exponent < -2:
        raise ValidationError("amount can have at most two decimal places")
    return int(value * 100)


def format_amount(pence: int) -> str:
    """Format whole pence as a decimal string, e.g. 1250 -> "12.50"."""
    sign = "-" if pence < 0 else ""
    pounds, remainder = divmod(abs(pence), 100)
    return f"{sign}{pounds}.{remainder:02d}"


def parse_date(text: str) -> date:
    """Parse an ISO date (YYYY-MM-DD)."""
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValidationError(f"not a valid date (expected YYYY-MM-DD): {text!r}") from None


def parse_month(text: str) -> tuple[int, int]:
    """Parse a month in YYYY-MM form into (year, month)."""
    parts = text.split("-")
    if len(parts) != 2 or not all(p.isdigit() for p in parts) or len(parts[0]) != 4:
        raise ValidationError(f"not a valid month (expected YYYY-MM): {text!r}")
    year, month = int(parts[0]), int(parts[1])
    if not 1 <= month <= 12:
        raise ValidationError(f"not a valid month (expected YYYY-MM): {text!r}")
    return year, month


def normalise_category(text: str) -> str:
    """Categories are case-insensitive and stored in lower case."""
    category = " ".join(text.split()).lower()
    if not category:
        raise ValidationError("category must not be empty")
    return category
