"""Run Part 1, 2 or 3 of the README and print each table with its timings."""

import argparse
import logging
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

lazy import pandas as pd
lazy import sqlalchemy as sa

from drug_formulary_tiers import pandas_solution, sql_solution
from drug_formulary_tiers.db import create_engine, load_formulary
from drug_formulary_tiers.schema import FormularyTable, TargetNotFoundError

type Method = Literal["pandas", "sql"]


@dataclass(frozen=True, slots=True)
class Part:
    table: FormularyTable
    target_id: str
    methods: tuple[Method, ...]


PARTS = frozendict(
    {
        1: Part("test_formulary", "00019356", ("pandas",)),
        2: Part("test_formulary", "00019356", ("sql",)),
        3: Part("formulary", "00022170", ("pandas", "sql")),
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


def run_pandas(connection: sa.Connection, table: str, target_id: str) -> None:
    timings = Timings()
    with timings.step("load Table-1"):
        formulary = load_formulary(connection, table)
    print(f"Table-1:\n{formulary}\n")

    with timings.step("Table-2"):
        comparison = pandas_solution.build_comparison_table(formulary, target_id)
    print(f"Table-2:\n{comparison}\n")

    with timings.step("Table-3"):
        all_tiers = pandas_solution.average_tier_difference(comparison)
        changed_tiers = pandas_solution.average_tier_difference(
            comparison, exclude_equal=True
        )
    print_table_3(all_tiers, changed_tiers)
    print(timings)


def run_sql(connection: sa.Connection, table: str, target_id: str) -> None:
    timings = Timings()
    with timings.step("Table-2"):
        comparison = sql_solution.build_comparison_table(connection, table, target_id)
    print(f"Table-2:\n{comparison}\n")

    with timings.step("Table-3"):
        all_tiers = sql_solution.average_tier_difference(connection, table, target_id)
        changed_tiers = sql_solution.average_tier_difference(
            connection, table, target_id, exclude_equal=True
        )
    print_table_3(all_tiers, changed_tiers)
    print(timings)


METHODS: frozendict[Method, Callable[[sa.Connection, str, str], None]] = frozendict(
    {"pandas": run_pandas, "sql": run_sql}
)


def print_table_3(all_tiers: pd.DataFrame, changed_tiers: pd.DataFrame) -> None:
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
        help="1: pandas on test_formulary, 2: SQL on test_formulary, "
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
    part = PARTS[args.part]
    target_id = args.target or part.target_id
    # Show every column of Table-2. Touching pandas here also keeps its import
    # time out of the timings.
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)

    engine = create_engine(args.database_url)
    try:
        with engine.connect() as connection:
            for method in part.methods:
                print(
                    f"== Part {args.part} with {method}: {part.table}, target {target_id}\n"
                )
                METHODS[method](connection, part.table, target_id)
    except TargetNotFoundError as error:
        print(f"formulary-tiers: error: {error} in {part.table}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0
