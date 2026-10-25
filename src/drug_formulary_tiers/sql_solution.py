"""Part 2: the same comparison with every join and aggregate done in SQL."""

lazy import pandas as pd
lazy import sqlalchemy as sa

from drug_formulary_tiers.schema import (
    UNCOVERED_TIER,
    TargetNotFoundError,
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


def _require_target(connection: sa.Connection, table: str, target_id: str) -> None:
    query = sa.text(
        f"SELECT 1 FROM {require_table(table)} WHERE formulary_id = :target_id LIMIT 1"
    )
    if connection.execute(query, {"target_id": target_id}).first() is None:
        raise TargetNotFoundError(target_id)


def build_comparison_table(
    connection: sa.Connection, table: str, target_id: str
) -> pd.DataFrame:
    """Table-2, computed in the database. See the pandas version for the rules."""
    _require_target(connection, table, target_id)
    return pd.read_sql_query(
        _comparison_query(table, _TABLE_2_SQL),
        connection,
        params={"target_id": target_id},
    )


def average_tier_difference(
    connection: sa.Connection,
    table: str,
    target_id: str,
    *,
    exclude_equal: bool = False,
) -> pd.DataFrame:
    """Table-3, computed in the database. See the pandas version for the rules."""
    _require_target(connection, table, target_id)
    difference = f"NULLIF({_DIFFERENCE}, 0)" if exclude_equal else _DIFFERENCE
    return pd.read_sql_query(
        _comparison_query(table, _TABLE_3_SQL.format(difference=difference)),
        connection,
        params={"target_id": target_id},
        dtype={"tier_difference": "float64"},
    )
