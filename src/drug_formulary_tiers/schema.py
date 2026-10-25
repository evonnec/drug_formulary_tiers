"""Table and column names, and the input checks both solutions rely on."""

import logging
from typing import Literal, cast, get_args

lazy import pandas as pd

logger = logging.getLogger(__name__)

type FormularyTable = Literal["test_formulary", "formulary"]
FORMULARY_TABLES: tuple[FormularyTable, ...] = get_args(FormularyTable.__value__)

# Tier assigned to a drug that one formulary in a comparison does not cover.
UNCOVERED_TIER = 7
COVERED_TIERS = range(1, 7)

KEY = ("formulary_id", "rxcui")
TABLE_1_COLUMNS = ("formulary_id", "tier_level_value", "rxcui")
TABLE_2_COLUMNS = (
    "formulary_target_id",
    "tier_level_value_target",
    "rxcui",
    "formulary_id",
    "tier_level_value",
)
TABLE_3_COLUMNS = ("formulary_id", "tier_difference")


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


def validate_formulary(formulary: pd.DataFrame) -> None:
    """Check Table-1 before comparing, since bad rows would skew the averages."""
    missing = set(TABLE_1_COLUMNS) - set(formulary.columns)
    if missing:
        raise FormularyDataError(f"missing columns: {sorted(missing)}")

    nulls = formulary[list(TABLE_1_COLUMNS)].isna().sum()
    if nulls.any():
        raise FormularyDataError(f"null values: {nulls[nulls > 0].to_dict()}")

    duplicated = formulary.duplicated(list(KEY), keep=False)
    if duplicated.any():
        example = formulary.loc[duplicated, list(KEY)].iloc[0].to_dict()
        raise FormularyDataError(
            f"{duplicated.sum()} rows share a (formulary_id, rxcui) key, e.g. {example}"
        )

    # Tiers outside 1-6 (the full dataset has some 7s) are kept but flagged: a
    # covered drug on tier 7 is indistinguishable from an uncovered one.
    outside = ~formulary["tier_level_value"].isin(COVERED_TIERS)
    if outside.any():
        logger.warning(
            "%d rows have a tier_level_value outside %d-%d: %s",
            outside.sum(),
            COVERED_TIERS.start,
            COVERED_TIERS.stop - 1,
            sorted(formulary.loc[outside, "tier_level_value"].unique().tolist()),
        )
