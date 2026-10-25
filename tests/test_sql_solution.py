"""The SQL solution, run on SQLite and (with TEST_DATABASE_URL) on Postgres."""

import logging

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from drug_formulary_tiers.schema import (
    TABLE_2_SCHEMA,
    TABLE_3_SCHEMA,
    FormularyDataError,
    TargetNotFoundError,
    polars_schema,
)
from drug_formulary_tiers.sql_solution import SqlComparison
from tests.helpers import README_TARGET, ConnectionFactory, formulary_frame


@pytest.mark.parametrize("table", ["test_formulary", "formulary"])
def test_comparison_table_matches_readme(
    connect: ConnectionFactory,
    readme_formulary: pl.DataFrame,
    readme_comparison: pl.DataFrame,
    table: str,
) -> None:
    with connect(readme_formulary) as connection:
        comparison = SqlComparison(connection, table, README_TARGET).comparison_table()

    assert_frame_equal(comparison, readme_comparison)


def test_average_tier_difference_matches_readme(
    connect: ConnectionFactory,
    readme_formulary: pl.DataFrame,
    readme_all_tiers: pl.DataFrame,
    readme_changed_tiers: pl.DataFrame,
) -> None:
    with connect(readme_formulary) as connection:
        query = SqlComparison(connection, "test_formulary", README_TARGET)
        all_tiers = query.average_tier_difference()
        changed_tiers = query.average_tier_difference(exclude_equal=True)

    assert_frame_equal(all_tiers, readme_all_tiers)
    assert_frame_equal(changed_tiers, readme_changed_tiers)


def test_reads_the_requested_table(
    connect: ConnectionFactory, readme_formulary: pl.DataFrame
) -> None:
    extra = formulary_frame([("00019500", 4, "1001")])
    with connect(readme_formulary, pl.concat([readme_formulary, extra])) as connection:
        test_ids = SqlComparison(connection, "test_formulary", README_TARGET)
        full_ids = SqlComparison(connection, "formulary", README_TARGET)

        assert "00019500" not in test_ids.average_tier_difference()["formulary_id"]
        assert "00019500" in full_ids.average_tier_difference()["formulary_id"]


def test_unknown_target_raises(
    connect: ConnectionFactory, readme_formulary: pl.DataFrame
) -> None:
    with connect(readme_formulary) as connection:
        with pytest.raises(TargetNotFoundError):
            SqlComparison(connection, "test_formulary", "00000000")


def test_target_id_is_bound_not_interpolated(
    connect: ConnectionFactory, readme_formulary: pl.DataFrame
) -> None:
    with connect(readme_formulary) as connection:
        with pytest.raises(TargetNotFoundError):
            SqlComparison(connection, "test_formulary", "x' OR '1'='1")


def test_unknown_table_is_rejected_before_querying(
    connect: ConnectionFactory, readme_formulary: pl.DataFrame
) -> None:
    with connect(readme_formulary) as connection:
        with pytest.raises(ValueError, match="unknown table"):
            SqlComparison(connection, "formulary; DROP TABLE formulary", README_TARGET)


def test_target_as_the_only_formulary_gives_empty_tables(
    connect: ConnectionFactory,
) -> None:
    with connect(formulary_frame([(README_TARGET, 1, "1001")])) as connection:
        query = SqlComparison(connection, "test_formulary", README_TARGET)
        comparison = query.comparison_table()
        averages = query.average_tier_difference()

    assert comparison.is_empty() and comparison.schema == polars_schema(TABLE_2_SCHEMA)
    assert averages.is_empty() and averages.schema == polars_schema(TABLE_3_SCHEMA)


def test_identical_formulary_has_no_part_b_average(connect: ConnectionFactory) -> None:
    formulary = formulary_frame(
        [(README_TARGET, 1, "1001"), ("00000001", 1, "1001"), ("00000002", 2, "1001")]
    )
    with connect(formulary) as connection:
        query = SqlComparison(connection, "test_formulary", README_TARGET)
        changed = dict(query.average_tier_difference(exclude_equal=True).iter_rows())

    assert changed == {"00000001": None, "00000002": -1.0}


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([(README_TARGET, 1, "1001"), (README_TARGET, 2, "1001")], "1 .formulary_id"),
        ([(README_TARGET, 1, "1001"), ("00000001", None, "1001")], "1 null"),
        ([(README_TARGET, 1, "1001"), ("00000001", 1, None)], "1 null"),
        ([(README_TARGET, 1, "1001"), (None, 1, "1001")], "1 null"),
    ],
    ids=["duplicate key", "null tier", "null rxcui", "null formulary_id"],
)
def test_unprotected_table_with_bad_rows_raises(
    connect: ConnectionFactory, rows: list[tuple[str, int, str]], message: str
) -> None:
    formulary = pl.DataFrame(
        rows, schema=["formulary_id", "tier_level_value", "rxcui"], orient="row"
    )
    with connect(formulary, constraints="") as connection:
        with pytest.raises(FormularyDataError, match=message):
            SqlComparison(connection, "test_formulary", README_TARGET)


def test_tier_outside_1_to_6_is_kept_with_a_warning(
    connect: ConnectionFactory, caplog: pytest.LogCaptureFixture
) -> None:
    formulary = formulary_frame([(README_TARGET, 7, "1001"), ("00000001", 1, "1001")])

    with connect(formulary) as connection, caplog.at_level(logging.WARNING):
        query = SqlComparison(connection, "test_formulary", README_TARGET)
        averages = query.average_tier_difference()

    assert "1 rows have a tier_level_value outside 1-6" in caplog.text
    assert averages["tier_difference"].to_list() == [6.0]
