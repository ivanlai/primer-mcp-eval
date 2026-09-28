"""Command-line interface: expenses add | list | categories | summary."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from expenses import __version__
from expenses.models import (
    ValidationError,
    format_amount,
    normalise_category,
    parse_amount,
    parse_date,
    parse_month,
)
from expenses.reports import in_category, in_month, month_summary
from expenses.storage import ExpenseStore, StorageError, default_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="expenses", description="Track your spending.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--file",
        type=Path,
        help="data file (default: $EXPENSES_FILE or ~/.expenses.json)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="record an expense")
    add.add_argument("amount", help="amount, e.g. 12.50")
    add.add_argument("category", help="category, e.g. groceries")
    add.add_argument("--note", default="", help="free-text note")
    add.add_argument("--date", help="date as YYYY-MM-DD (default: today)")

    lst = sub.add_parser("list", help="list expenses")
    lst.add_argument("--month", help="only this month, as YYYY-MM")
    lst.add_argument("--category", help="only this category")

    sub.add_parser("categories", help="list categories in use")

    summary = sub.add_parser("summary", help="summarise one month")
    summary.add_argument("month", help="month as YYYY-MM")

    return parser


def cmd_add(store: ExpenseStore, args: argparse.Namespace) -> int:
    amount = parse_amount(args.amount)
    category = normalise_category(args.category)
    when = parse_date(args.date) if args.date else date.today()
    expense = store.add(when, amount, category, args.note.strip())
    print(f"Added #{expense.id}: {format_amount(amount)} {category} on {when.isoformat()}")
    return 0


def cmd_list(store: ExpenseStore, args: argparse.Namespace) -> int:
    expenses = store.all()
    if args.month:
        year, month = parse_month(args.month)
        expenses = in_month(expenses, year, month)
    if args.category:
        expenses = in_category(expenses, normalise_category(args.category))
    if not expenses:
        print("No expenses found.")
        return 0
    for e in expenses:
        line = f"#{e.id:<4} {e.date.isoformat()}  {format_amount(e.amount_pence):>10}  {e.category}"
        if e.note:
            line += f"  ({e.note})"
        print(line)
    total = sum(e.amount_pence for e in expenses)
    print(f"{len(expenses)} expense(s), total {format_amount(total)}")
    return 0


def cmd_categories(store: ExpenseStore, args: argparse.Namespace) -> int:
    categories = store.categories()
    if not categories:
        print("No categories yet.")
        return 0
    for category in categories:
        print(category)
    return 0


def cmd_summary(store: ExpenseStore, args: argparse.Namespace) -> int:
    year, month = parse_month(args.month)
    summary = month_summary(store.all(), year, month)
    print(f"Summary for {year:04d}-{month:02d}")
    if not summary.count:
        print("No expenses this month.")
        return 0
    print(f"Total:          {format_amount(summary.total_pence)} ({summary.count} expenses)")
    print(f"Daily average:  {format_amount(summary.daily_average_pence)}")
    print("By category:")
    for item in summary.by_category:
        print(
            f"  {item.category:<16} {format_amount(item.total_pence):>10}"
            f"  {item.share_percent:>3}%  ({item.count})"
        )
    return 0


COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "categories": cmd_categories,
    "summary": cmd_summary,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = ExpenseStore(args.file or default_path())
        return COMMANDS[args.command](store, args)
    except (ValidationError, StorageError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
