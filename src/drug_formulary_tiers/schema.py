"""Table schemas, and the input checks both solutions rely on."""

import logging
from collections.abc import Mapping
from typing import Literal, cast, get_args

lazy import polars as pl

logger = logging.getLogger(__name__)

type FormularyTable = Literal["test_formulary", "formulary"]
FORMULARY_TABLES: tuple[FormularyTable, ...] = get_args(FormularyTable.__value__)

# Tier assigned to a drug that one formulary in a comparison does not cover.
UNCOVERED_TIER = 7
COVERED_TIERS = range(1, 7)

# Python types rather than polars dtypes, so importing this module doesn't
# import polars; polars reads str, int and float as String, Int64 and Float64.
KEY = ("formulary_id", "rxcui")
TABLE_1_SCHEMA = frozendict(
    {"formulary_id": str, "tier_level_value": int, "rxcui": str}
)
TABLE_2_SCHEMA = frozendict(
    {
        "formulary_target_id": str,
        "tier_level_value_target": int,
        "rxcui": str,
        "formulary_id": str,
        "tier_level_value": int,
    }
)
TABLE_3_SCHEMA = frozendict({"formulary_id": str, "tier_difference": float})


def polars_schema(schema: Mapping[str, type]) -> pl.Schema:
    return pl.Schema(schema)


class FormularyDataError(ValueError):
    """The formulary data breaks an assumption the comparison depends on."""


class TargetNotFoundError(LookupError):
    """The target formulary_id has no drugs in the data."""

    def __init__(self, target_id: str) -> None:
        super().__init__(f"target formulary_id {target_id!r} not found")
        self.target_id = target_id


def require_table(table: str) -> FormularyTable:
    """Return `table` if it is a known formulary table, so it is safe to put in SQL."""
    if table not in FORMULARY_TABLES:
        raise ValueError(f"unknown table {table!r}, expected one of {FORMULARY_TABLES}")
    return cast(FormularyTable, table)


def check_counts(*, duplicate_keys: int, nulls: int, outside_tiers: int) -> None:
    """Raise or warn on the problem counts either solution found in its input."""
    if nulls:
        raise FormularyDataError(f"{nulls} null formulary_id, tier or rxcui values")
    if duplicate_keys:
        raise FormularyDataError(
            f"{duplicate_keys} (formulary_id, rxcui) keys appear more than once"
        )
    # Tiers outside 1-6 (the full dataset has some 7s) are kept but flagged: a
    # covered drug on tier 7 is indistinguishable from an uncovered one.
    if outside_tiers:
        logger.warning(
            "%d rows have a tier_level_value outside %d-%d",
            outside_tiers,
            COVERED_TIERS.start,
            COVERED_TIERS.stop - 1,
        )


def validate_formulary(formulary: pl.DataFrame) -> None:
    """Check Table-1 before comparing, since bad rows would skew the averages."""
    missing = set(TABLE_1_SCHEMA) - set(formulary.columns)
    if missing:
        raise FormularyDataError(f"missing columns: {sorted(missing)}")

    for column, expected in TABLE_1_SCHEMA.items():
        dtype = formulary.schema[column]
        if not (dtype.is_integer() if expected is int else dtype == pl.String):
            raise FormularyDataError(
                f"{column} is {dtype}, expected {pl.Int64 if expected is int else pl.String}"
            )

    tier = pl.col("tier_level_value")
    covered = tier.is_between(COVERED_TIERS.start, COVERED_TIERS.stop - 1)
    nulls, outside_tiers = formulary.select(
        pl.sum_horizontal(pl.col(*TABLE_1_SCHEMA).null_count()), (~covered).sum()
    ).row(0)
    check_counts(
        duplicate_keys=formulary.group_by(KEY).len().filter(pl.col("len") > 1).height,
        nulls=nulls,
        outside_tiers=outside_tiers,
    )
