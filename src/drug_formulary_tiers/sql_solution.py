"""Part 2: the same comparison with every join and aggregate done in SQL."""

lazy import polars as pl
lazy import sqlalchemy as sa

from drug_formulary_tiers.schema import (
    COVERED_TIERS,
    TABLE_2_SCHEMA,
    TABLE_3_SCHEMA,
    UNCOVERED_TIER,
    TargetNotFoundError,
    check_counts,
    polars_schema,
    require_table,
)

# Table-2 as a CTE. The table name is checked against FORMULARY_TABLES before it
# is formatted in; the target formulary_id is always a bind parameter.
_COMPARISON_CTE = """
WITH target AS (
    SELECT rxcui, tier_level_value
    FROM {table}
    WHERE formulary_id = :target_id
),
others AS (
    SELECT formulary_id, rxcui, tier_level_value
    FROM {table}
    WHERE formulary_id <> :target_id
),
-- Every other formulary paired with every target drug, so a drug the formulary
-- lacks still gets a row; the full join then adds the drugs the target lacks.
target_drugs AS (
    SELECT f.formulary_id, t.rxcui, t.tier_level_value
    FROM (
        SELECT DISTINCT formulary_id FROM {table} WHERE formulary_id <> :target_id
    ) AS f
    CROSS JOIN target AS t
),
comparison AS (
    SELECT
        CAST(:target_id AS TEXT) AS formulary_target_id,
        COALESCE(d.tier_level_value, {uncovered}) AS tier_level_value_target,
        COALESCE(d.rxcui, o.rxcui) AS rxcui,
        COALESCE(d.formulary_id, o.formulary_id) AS formulary_id,
        COALESCE(o.tier_level_value, {uncovered}) AS tier_level_value
    FROM target_drugs AS d
    FULL OUTER JOIN others AS o
        ON o.formulary_id = d.formulary_id AND o.rxcui = d.rxcui
)
"""

_TABLE_2_SQL = """
SELECT * FROM comparison
ORDER BY formulary_id, rxcui
"""

# NULLIF turns equal tiers into NULLs, which AVG skips, for part B. A formulary
# whose drugs all match the target keeps its row with a NULL average.
_TABLE_3_SQL = """
SELECT
    formulary_id,
    CAST(AVG({difference}) AS DOUBLE PRECISION) AS tier_difference
FROM comparison
GROUP BY formulary_id
ORDER BY formulary_id
"""

_DIFFERENCE = "tier_level_value_target - tier_level_value"


def _comparison_query(table: str, select: str) -> sa.TextClause:
    cte = _COMPARISON_CTE.format(table=require_table(table), uncovered=UNCOVERED_TIER)
    return sa.text(cte + select)


# The same checks the polars solution makes on Table-1. The primary key in
# db/01-init.sh already rules out nulls and duplicates there, but other databases
# (or tables built some other way) may not.
_CHECK_SQL = """
SELECT
    (SELECT count(*) FROM (
        SELECT 1 FROM {table} GROUP BY formulary_id, rxcui HAVING count(*) > 1
    ) AS duplicates) AS duplicate_keys,
    3 * count(*) - count(formulary_id) - count(tier_level_value) - count(rxcui)
        AS nulls,
    count(CASE WHEN tier_level_value NOT BETWEEN {low} AND {high} THEN 1 END)
        AS outside_tiers,
    count(CASE WHEN formulary_id = :target_id THEN 1 END) AS target_rows
FROM {table}
"""


class SqlComparison:
    """Table-2 and Table-3 against one target, computed in the database.

    The table is checked once, when this is created, with the same rules as
    `polars_solution.build_comparison_table`.
    """

    def __init__(self, connection: sa.Connection, table: str, target_id: str) -> None:
        self.connection = connection
        self.table = require_table(table)
        self.target_id = target_id

        check = _CHECK_SQL.format(
            table=self.table, low=COVERED_TIERS.start, high=COVERED_TIERS.stop - 1
        )
        counts = connection.execute(sa.text(check), self._parameters).one()
        check_counts(
            duplicate_keys=counts.duplicate_keys,
            nulls=counts.nulls,
            outside_tiers=counts.outside_tiers,
        )
        if not counts.target_rows:
            raise TargetNotFoundError(target_id)

    @property
    def _parameters(self) -> dict[str, str]:
        return {"target_id": self.target_id}

    def comparison_table(self) -> pl.DataFrame:
        """Table-2."""
        return pl.read_database(
            _comparison_query(self.table, _TABLE_2_SQL),
            self.connection,
            execute_options={"parameters": self._parameters},
            schema_overrides=polars_schema(TABLE_2_SCHEMA),
        )

    def average_tier_difference(self, *, exclude_equal: bool = False) -> pl.DataFrame:
        """Table-3, for part B with `exclude_equal`."""
        difference = f"NULLIF({_DIFFERENCE}, 0)" if exclude_equal else _DIFFERENCE
        return pl.read_database(
            _comparison_query(self.table, _TABLE_3_SQL.format(difference=difference)),
            self.connection,
            execute_options={"parameters": self._parameters},
            schema_overrides=polars_schema(TABLE_3_SCHEMA),
        )
