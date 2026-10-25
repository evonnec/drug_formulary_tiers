import logging
import math

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from drug_formulary_tiers.pandas_solution import (
    average_tier_difference,
    build_comparison_table,
)
from drug_formulary_tiers.schema import (
    TABLE_2_COLUMNS,
    TABLE_3_COLUMNS,
    FormularyDataError,
    TargetNotFoundError,
)
from tests.helpers import README_TARGET, formulary_frame


def test_comparison_table_matches_readme(
    readme_formulary: pd.DataFrame, readme_comparison: pd.DataFrame
) -> None:
    comparison = build_comparison_table(readme_formulary, README_TARGET)

    assert_frame_equal(comparison, readme_comparison)


def test_average_tier_difference_matches_readme(
    readme_comparison: pd.DataFrame,
    readme_all_tiers: pd.DataFrame,
    readme_changed_tiers: pd.DataFrame,
) -> None:
    assert_frame_equal(average_tier_difference(readme_comparison), readme_all_tiers)
    assert_frame_equal(
        average_tier_difference(readme_comparison, exclude_equal=True),
        readme_changed_tiers,
    )


def test_target_is_not_compared_with_itself(readme_formulary: pd.DataFrame) -> None:
    comparison = build_comparison_table(readme_formulary, README_TARGET)

    assert README_TARGET not in set(comparison.formulary_id)
    assert set(comparison.formulary_target_id) == {README_TARGET}


def test_formulary_sharing_no_drugs_is_compared_on_both_sets(
    readme_formulary: pd.DataFrame,
) -> None:
    comparison = build_comparison_table(readme_formulary, README_TARGET)
    disjoint = comparison[comparison.formulary_id == "00019400"]

    # 3 target drugs it lacks plus 3 drugs the target lacks, all uncovered on one side
    assert len(disjoint) == 6
    assert (
        (disjoint.tier_level_value_target == 7) ^ (disjoint.tier_level_value == 7)
    ).all()


def test_result_does_not_depend_on_row_order_or_index(
    readme_formulary: pd.DataFrame, readme_comparison: pd.DataFrame
) -> None:
    shuffled = readme_formulary.sample(frac=1, random_state=0)
    shuffled.index = shuffled.index * 10

    assert_frame_equal(
        build_comparison_table(shuffled, README_TARGET), readme_comparison
    )


def test_input_is_not_modified(readme_formulary: pd.DataFrame) -> None:
    before = readme_formulary.copy()

    build_comparison_table(readme_formulary, README_TARGET)

    assert_frame_equal(readme_formulary, before)


def test_formulary_ids_keep_leading_zeros(readme_formulary: pd.DataFrame) -> None:
    comparison = build_comparison_table(readme_formulary, README_TARGET)

    assert set(comparison.formulary_id) == {
        "00019100",
        "00019200",
        "00019300",
        "00019400",
    }


def test_unknown_target_raises(readme_formulary: pd.DataFrame) -> None:
    with pytest.raises(TargetNotFoundError, match="'00000000'"):
        build_comparison_table(readme_formulary, "00000000")


def test_target_as_the_only_formulary_gives_empty_tables() -> None:
    formulary = formulary_frame([(README_TARGET, 1, "1001")])

    comparison = build_comparison_table(formulary, README_TARGET)
    averages = average_tier_difference(comparison)

    assert comparison.empty and list(comparison.columns) == list(TABLE_2_COLUMNS)
    assert averages.empty and list(averages.columns) == list(TABLE_3_COLUMNS)


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

    all_tiers = average_tier_difference(comparison).set_index("formulary_id")
    changed = average_tier_difference(comparison, exclude_equal=True).set_index(
        "formulary_id"
    )

    assert all_tiers.tier_difference.to_dict() == {"00000001": 0.0, "00000002": -3.0}
    # every drug matches, so B has nothing to average but keeps the row
    assert math.isnan(changed.tier_difference["00000001"])
    # 1001: 1 - 2, 1002: 2 - 7 (uncovered)
    assert changed.tier_difference["00000002"] == -3.0


@pytest.mark.parametrize(
    ("formulary", "message"),
    [
        (pd.DataFrame({"formulary_id": ["1"], "rxcui": ["1"]}), "missing columns"),
        (formulary_frame([("1", 1, "1"), ("2", 1, None)]), "null values"),  # type: ignore[list-item]
        (formulary_frame([("1", 1, "1"), ("1", 2, "1")]), "share a"),
    ],
    ids=["missing column", "null rxcui", "duplicate key"],
)
def test_invalid_formulary_raises(formulary: pd.DataFrame, message: str) -> None:
    with pytest.raises(FormularyDataError, match=message):
        build_comparison_table(formulary, "1")


def test_tier_outside_1_to_6_is_kept_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    formulary = formulary_frame([(README_TARGET, 7, "1001"), ("00000001", 1, "1001")])

    with caplog.at_level(logging.WARNING):
        comparison = build_comparison_table(formulary, README_TARGET)

    assert "1 rows have a tier_level_value outside 1-6: [7]" in caplog.text
    assert average_tier_difference(comparison).tier_difference.tolist() == [6.0]
