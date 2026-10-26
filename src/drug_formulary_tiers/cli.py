"""Run Part 1, 2 or 3 of the README and print each table with its timings."""

import argparse
import io
import logging
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

lazy import polars as pl
lazy import sqlalchemy as sa

from drug_formulary_tiers import polars_solution, sql_solution
from drug_formulary_tiers.db import create_engine, load_formulary
from drug_formulary_tiers.schema import (
    FormularyDataError,
    FormularyTable,
    TargetNotFoundError,
)

type Method = Literal["polars", "sql"]


@dataclass(frozen=True, slots=True)
class Part:
    table: FormularyTable
    target_id: str
    methods: tuple[Method, ...]


PARTS = frozendict(
    {
        1: Part("test_formulary", "00019356", ("polars",)),
        2: Part("test_formulary", "00019356", ("sql",)),
        3: Part("formulary", "00022170", ("polars", "sql")),
    }
)


class Timings:
    """Wall-clock time of each step, printed once a method finishes."""

    def __init__(self) -> None:
        self.steps: dict[str, float] = {}

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.steps[name] = time.perf_counter() - start

    def __str__(self) -> str:
        steps = ", ".join(f"{name} {secs:.2f}s" for name, secs in self.steps.items())
        return f"Execution time: {sum(self.steps.values()):.2f}s ({steps})"


def run_polars(connection: sa.Connection, table: str, target_id: str) -> None:
    timings = Timings()
    with timings.step("load Table-1"):
        formulary = load_formulary(connection, table)
    print(f"Table-1:\n{formulary}\n")

    with timings.step("Table-2"):
        comparison = polars_solution.build_comparison_table(formulary, target_id)
    print(f"Table-2:\n{comparison}\n")

    with timings.step("Table-3"):
        all_tiers = polars_solution.average_tier_difference(comparison)
        changed_tiers = polars_solution.average_tier_difference(
            comparison, exclude_equal=True
        )
    print_table_3(all_tiers, changed_tiers)
    print(timings)


def run_sql(connection: sa.Connection, table: str, target_id: str) -> None:
    timings = Timings()
    with timings.step("check"):
        query = sql_solution.SqlComparison(connection, table, target_id)

    with timings.step("Table-2"):
        comparison = query.comparison_table()
    print(f"Table-2:\n{comparison}\n")

    with timings.step("Table-3"):
        all_tiers, changed_tiers = query.average_tier_differences()
    print_table_3(all_tiers, changed_tiers)
    print(timings)


METHODS: frozendict[Method, Callable[[sa.Connection, str, str], None]] = frozendict(
    {"polars": run_polars, "sql": run_sql}
)


def print_table_3(all_tiers: pl.DataFrame, changed_tiers: pl.DataFrame) -> None:
    print(f"Table-3 (A), all drugs:\n{all_tiers}\n")
    print(f"Table-3 (B), drugs on different tiers:\n{changed_tiers}\n")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="formulary-tiers",
        description="Average drug tier difference between each formulary and a target.",
        suggest_on_error=True,
    )
    parser.add_argument(
        "part",
        type=int,
        choices=PARTS,
        help="1: polars on test_formulary, 2: SQL on test_formulary, "
        "3: both on formulary",
    )
    parser.add_argument(
        "--target",
        help="target formulary_id (default: the README's target for the part)",
    )
    parser.add_argument(
        "--database-url",
        help="SQLAlchemy URL (default: $DATABASE_URL, else the docker compose database)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(format="%(levelname)s: %(message)s")
    # Keep the headers, tables and warnings in order when output is piped.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)
    part = PARTS[args.part]
    target_id = part.target_id if args.target is None else args.target
    # Show every column of Table-2. Touching polars here also keeps its import
    # time out of the timings.
    pl.Config.set_tbl_cols(-1)
    pl.Config.set_tbl_width_chars(120)

    try:
        engine = create_engine(args.database_url)
    except (sa.exc.ArgumentError, ImportError) as error:
        # A URL SQLAlchemy can't parse, or whose driver isn't installed. The URL
        # itself isn't echoed, since it may hold a password.
        return fail(f"cannot use the database URL: {error}")
    try:
        with engine.connect() as connection:
            for method in part.methods:
                print(
                    f"== Part {args.part} with {method}: {part.table}, target {target_id}\n"
                )
                METHODS[method](connection, part.table, target_id)
    except TargetNotFoundError as error:
        return fail(f"{error} in {part.table}")
    except FormularyDataError as error:
        return fail(f"invalid data in {part.table}: {error}")
    except sa.exc.SQLAlchemyError as error:
        return fail(f"database error: {str(error).splitlines()[0]}")
    finally:
        engine.dispose()
    return 0


def fail(message: str) -> int:
    print(f"formulary-tiers: error: {message}", file=sys.stderr)
    return 1
