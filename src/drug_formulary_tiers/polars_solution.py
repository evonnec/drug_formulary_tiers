"""Part 1: compare every formulary against a target using polars joins."""

lazy import polars as pl

from drug_formulary_tiers.schema import (
    KEY,
    TABLE_2_SCHEMA,
    TABLE_3_SCHEMA,
    UNCOVERED_TIER,
    TargetNotFoundError,
    polars_schema,
    validate_formulary,
)


def build_comparison_table(formulary: pl.DataFrame, target_id: str) -> pl.DataFrame:
    """Table-2: each formulary's drugs lined up against the target formulary's.

    Every formulary other than the target is compared on the union of its drugs
    and the target's; a drug missing from either side gets `UNCOVERED_TIER`.
    """
    validate_formulary(formulary)
    is_target = pl.col("formulary_id") == target_id
    if formulary.filter(is_target).is_empty():
        raise TargetNotFoundError(target_id)

    rows = formulary.lazy()
    target = rows.filter(is_target).select(
        "rxcui", tier_level_value_target="tier_level_value"
    )
    others = rows.filter(~is_target).select(*KEY, "tier_level_value")

    # Pairing every other formulary with every target drug gives the drugs a
    # formulary lacks a row; the full join then adds the drugs the target lacks.
    # This stays linear in the size of Table-2, unlike a self-join on rxcui alone.
    target_drugs = others.select("formulary_id").unique().join(target, how="cross")
    tiers = ["tier_level_value_target", "tier_level_value"]
    return (
        target_drugs.join(others, on=KEY, how="full", coalesce=True)
        .with_columns(
            pl.col(tiers).fill_null(UNCOVERED_TIER),
            formulary_target_id=pl.lit(target_id),
        )
        .select(*TABLE_2_SCHEMA)
        .cast(polars_schema(TABLE_2_SCHEMA))
        .sort(KEY)
        .collect()
    )


def average_tier_difference(
    comparison: pl.DataFrame, *, exclude_equal: bool = False
) -> pl.DataFrame:
    """Table-3: mean `tier_level_value_target - tier_level_value` per formulary.

    With `exclude_equal` (part B) drugs on the same tier are left out; a formulary
    whose drugs all match the target keeps its row with a null average.
    """
    difference = pl.col("tier_level_value_target") - pl.col("tier_level_value")
    if exclude_equal:
        difference = pl.when(difference != 0).then(difference)
    return (
        comparison.group_by("formulary_id")
        .agg(tier_difference=difference.mean())
        .sort("formulary_id")
        .cast(polars_schema(TABLE_3_SCHEMA))
    )
