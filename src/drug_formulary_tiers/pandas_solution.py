"""Part 1: compare every formulary against a target using pandas merges."""

lazy import pandas as pd

from drug_formulary_tiers.schema import (
    KEY,
    TABLE_1_COLUMNS,
    TABLE_2_COLUMNS,
    UNCOVERED_TIER,
    TargetNotFoundError,
    validate_formulary,
)


def build_comparison_table(formulary: pd.DataFrame, target_id: str) -> pd.DataFrame:
    """Table-2: each formulary's drugs lined up against the target formulary's.

    Every formulary other than the target is compared on the union of its drugs
    and the target's; a drug missing from either side gets `UNCOVERED_TIER`.
    """
    validate_formulary(formulary)
    is_target = formulary["formulary_id"] == target_id
    if not is_target.any():
        raise TargetNotFoundError(target_id)

    target = formulary.loc[is_target, ["rxcui", "tier_level_value"]]
    others = formulary.loc[~is_target, list(TABLE_1_COLUMNS)]

    # Pairing every other formulary with every target drug gives the drugs a
    # formulary lacks a row; the outer merge then adds the drugs the target lacks.
    # This stays linear in the size of Table-2, unlike a self-join on rxcui alone.
    target_drugs = others[["formulary_id"]].drop_duplicates().merge(target, how="cross")
    comparison = target_drugs.merge(
        others, on=list(KEY), how="outer", suffixes=("_target", "")
    )

    tiers = ["tier_level_value_target", "tier_level_value"]
    comparison[tiers] = comparison[tiers].fillna(UNCOVERED_TIER).astype("int64")
    return (
        comparison.assign(formulary_target_id=target_id)
        .loc[:, list(TABLE_2_COLUMNS)]
        .sort_values(["formulary_id", "rxcui"], ignore_index=True)
    )


def average_tier_difference(
    comparison: pd.DataFrame, *, exclude_equal: bool = False
) -> pd.DataFrame:
    """Table-3: mean `tier_level_value_target - tier_level_value` per formulary.

    With `exclude_equal` (part B) drugs on the same tier are left out; a formulary
    whose drugs all match the target keeps its row with a NaN average.
    """
    difference = comparison["tier_level_value_target"] - comparison["tier_level_value"]
    if exclude_equal:
        difference = difference.where(difference != 0)
    return (
        difference.astype("float64")
        .groupby(comparison["formulary_id"])
        .mean()
        .rename("tier_difference")
        .reset_index()
    )
