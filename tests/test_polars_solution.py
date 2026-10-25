import logging

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from drug_formulary_tiers.polars_solution import (
    average_tier_difference,
    build_comparison_table,
)
from drug_formulary_tiers.schema import (
    TABLE_2_SCHEMA,
    TABLE_3_SCHEMA,
    FormularyDataError,
    TargetNotFoundError,
    polars_schema,
)
from tests.helpers import README_TARGET, formulary_frame


def test_comparison_table_matches_readme(
    readme_formulary: pl.DataFrame, readme_comparison: pl.DataFrame
) -> None:
    comparison = build_comparison_table(readme_formulary, README_TARGET)

    assert_frame_equal(comparison, readme_comparison)


def test_average_tier_difference_matches_readme(
    readme_comparison: pl.DataFrame,
    readme_all_tiers: pl.DataFrame,
    readme_changed_tiers: pl.DataFrame,
) -> None:
    assert_frame_equal(average_tier_difference(readme_comparison), readme_all_tiers)
    assert_frame_equal(
        average_tier_difference(readme_comparison, exclude_equal=True),
        readme_changed_tiers,
    )


def test_target_is_not_compared_with_itself(readme_formulary: pl.DataFrame) -> None:
    comparison = build_comparison_table(readme_formulary, README_TARGET)

    assert README_TARGET not in comparison["formulary_id"]
    assert comparison["formulary_target_id"].unique().to_list() == [README_TARGET]


def test_formulary_sharing_no_drugs_is_compared_on_both_sets(
    readme_formulary: pl.DataFrame,
) -> None:
    comparison = build_comparison_table(readme_formulary, README_TARGET)
    disjoint = comparison.filter(pl.col("formulary_id") == "00019400")

    # 3 target drugs it lacks plus 3 drugs the target lacks, uncovered on one side
    assert disjoint.height == 6
    uncovered = (pl.col("tier_level_value_target") == 7) ^ (
        pl.col("tier_level_value") == 7
    )
    assert disjoint.select(uncovered.all()).item()


def test_result_does_not_depend_on_row_order(
    readme_formulary: pl.DataFrame, readme_comparison: pl.DataFrame
) -> None:
    shuffled = readme_formulary.sample(fraction=1, shuffle=True, seed=0)

    assert_frame_equal(
        build_comparison_table(shuffled, README_TARGET), readme_comparison
    )


def test_extra_columns_and_narrow_integer_tiers_are_accepted(
    readme_formulary: pl.DataFrame, readme_comparison: pl.DataFrame
) -> None:
    formulary = readme_formulary.with_columns(
        pl.col("tier_level_value").cast(pl.Int16), ndc=pl.lit("00002143380")
    )

    assert_frame_equal(
        build_comparison_table(formulary, README_TARGET), readme_comparison
    )


def test_unknown_target_raises(readme_formulary: pl.DataFrame) -> None:
    with pytest.raises(TargetNotFoundError, match="'00000000'"):
        build_comparison_table(readme_formulary, "00000000")


def test_target_as_the_only_formulary_gives_empty_tables() -> None:
    formulary = formulary_frame([(README_TARGET, 1, "1001")])

    comparison = build_comparison_table(formulary, README_TARGET)
    averages = average_tier_difference(comparison)

    assert comparison.is_empty() and comparison.schema == polars_schema(TABLE_2_SCHEMA)
    assert averages.is_empty() and averages.schema == polars_schema(TABLE_3_SCHEMA)


def test_identical_formulary_has_no_part_b_average() -> None:
    formulary = formulary_frame(
        [
            (README_TARGET, 1, "1001"),
            (README_TARGET, 2, "1002"),
            ("00000001", 1, "1001"),
            ("00000001", 2, "1002"),
            ("00000002", 2, "1001"),
        ]
    )
    comparison = build_comparison_table(formulary, README_TARGET)

    all_tiers = dict(average_tier_difference(comparison).iter_rows())
    changed = dict(average_tier_difference(comparison, exclude_equal=True).iter_rows())

    # 00000002: 1001 is 1 - 2 and 1002 is 2 - 7 (uncovered)
    assert all_tiers == {"00000001": 0.0, "00000002": -3.0}
    # every drug matches, so B has nothing to average but keeps the row
    assert changed == {"00000001": None, "00000002": -3.0}


@pytest.mark.parametrize(
    ("formulary", "message"),
    [
        (pl.DataFrame({"formulary_id": ["1"], "rxcui": ["1"]}), "missing columns"),
        (
            pl.DataFrame(
                {"formulary_id": ["1"], "tier_level_value": [1.9], "rxcui": ["1"]}
            ),
            "tier_level_value is Float64, expected Int64",
        ),
        (
            pl.DataFrame(
                {"formulary_id": ["1"], "tier_level_value": ["1"], "rxcui": ["1"]}
            ),
            "tier_level_value is String, expected Int64",
        ),
        (
            pl.DataFrame(
                {"formulary_id": [1], "tier_level_value": [1], "rxcui": ["1"]}
            ),
            "formulary_id is Int64, expected String",
        ),
        (
            formulary_frame([("1", 1, "1"), ("2", 1, None)]),  # type: ignore[list-item]
            "1 null",
        ),
        (
            formulary_frame(
                [("1", 1, "1"), ("1", 2, "1"), ("2", 1, "5"), ("2", 1, "5")]
            ),
            "2 .formulary_id, rxcui. keys appear more than once",
        ),
    ],
    ids=[
        "missing column",
        "fractional tier",
        "string tier",
        "integer formulary_id",
        "null rxcui",
        "duplicate keys",
    ],
)
def test_invalid_formulary_raises(formulary: pl.DataFrame, message: str) -> None:
    with pytest.raises(FormularyDataError, match=message):
        build_comparison_table(formulary, "1")


def test_tier_outside_1_to_6_is_kept_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    formulary = formulary_frame([(README_TARGET, 7, "1001"), ("00000001", 1, "1001")])

    with caplog.at_level(logging.WARNING):
        comparison = build_comparison_table(formulary, README_TARGET)

    assert "1 rows have a tier_level_value outside 1-6" in caplog.text
    assert average_tier_difference(comparison)["tier_difference"].to_list() == [6.0]
