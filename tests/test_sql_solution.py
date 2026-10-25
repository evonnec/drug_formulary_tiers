"""The SQL solution, run on SQLite and (with TEST_DATABASE_URL) on Postgres."""

import math

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from drug_formulary_tiers.schema import TargetNotFoundError
from drug_formulary_tiers.sql_solution import (
    average_tier_difference,
    build_comparison_table,
)
from tests.helpers import README_TARGET, ConnectionFactory, formulary_frame


@pytest.mark.parametrize("table", ["test_formulary", "formulary"])
def test_comparison_table_matches_readme(
    connect: ConnectionFactory,
    readme_formulary: pd.DataFrame,
    readme_comparison: pd.DataFrame,
    table: str,
) -> None:
    with connect(readme_formulary) as connection:
        comparison = build_comparison_table(connection, table, README_TARGET)

    assert_frame_equal(comparison, readme_comparison)


def test_average_tier_difference_matches_readme(
    connect: ConnectionFactory,
    readme_formulary: pd.DataFrame,
    readme_all_tiers: pd.DataFrame,
    readme_changed_tiers: pd.DataFrame,
) -> None:
    with connect(readme_formulary) as connection:
        all_tiers = average_tier_difference(connection, "test_formulary", README_TARGET)
        changed_tiers = average_tier_difference(
            connection, "test_formulary", README_TARGET, exclude_equal=True
        )

    assert_frame_equal(all_tiers, readme_all_tiers)
    assert_frame_equal(changed_tiers, readme_changed_tiers)


def test_unknown_target_raises(
    connect: ConnectionFactory, readme_formulary: pd.DataFrame
) -> None:
    with connect(readme_formulary) as connection:
        with pytest.raises(TargetNotFoundError):
            build_comparison_table(connection, "test_formulary", "00000000")
        with pytest.raises(TargetNotFoundError):
            average_tier_difference(connection, "test_formulary", "00000000")


def test_target_id_is_bound_not_interpolated(
    connect: ConnectionFactory, readme_formulary: pd.DataFrame
) -> None:
    with connect(readme_formulary) as connection:
        with pytest.raises(TargetNotFoundError):
            average_tier_difference(connection, "test_formulary", "x' OR '1'='1")


def test_unknown_table_is_rejected_before_querying(
    connect: ConnectionFactory, readme_formulary: pd.DataFrame
) -> None:
    with connect(readme_formulary) as connection:
        with pytest.raises(ValueError, match="unknown table"):
            build_comparison_table(
                connection, "formulary; DROP TABLE formulary", README_TARGET
            )


def test_target_as_the_only_formulary_gives_empty_tables(
    connect: ConnectionFactory,
) -> None:
    with connect(formulary_frame([(README_TARGET, 1, "1001")])) as connection:
        comparison = build_comparison_table(connection, "test_formulary", README_TARGET)
        averages = average_tier_difference(connection, "test_formulary", README_TARGET)

    assert comparison.empty
    assert averages.empty


def test_identical_formulary_has_no_part_b_average(connect: ConnectionFactory) -> None:
    formulary = formulary_frame(
        [(README_TARGET, 1, "1001"), ("00000001", 1, "1001"), ("00000002", 2, "1001")]
    )
    with connect(formulary) as connection:
        changed = average_tier_difference(
            connection, "test_formulary", README_TARGET, exclude_equal=True
        )

    assert changed.formulary_id.tolist() == ["00000001", "00000002"]
    assert math.isnan(changed.tier_difference[0])
    assert changed.tier_difference[1] == -1.0
