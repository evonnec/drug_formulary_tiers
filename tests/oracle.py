"""Brute-force reference for Table-3, written straight from the README rules.

It shares no code with the package, so the property tests compare two
independent readings of the spec.
"""

import math
from collections import defaultdict
from collections.abc import Iterable
from statistics import fmean

UNCOVERED_TIER = 7

type Averages = dict[str, float]


def expected_tier_differences(
    rows: Iterable[tuple[str, int, str]], target_id: str
) -> tuple[Averages, Averages]:
    """(A, B) averages per formulary_id from (formulary_id, tier, rxcui) rows."""
    tiers: defaultdict[str, dict[str, int]] = defaultdict(dict)
    for formulary_id, tier, rxcui in rows:
        tiers[formulary_id][rxcui] = tier

    target = tiers[target_id]
    all_drugs: Averages = {}
    changed_drugs: Averages = {}
    for formulary_id, drugs in tiers.items():
        if formulary_id == target_id:
            continue
        differences = [
            target.get(rxcui, UNCOVERED_TIER) - drugs.get(rxcui, UNCOVERED_TIER)
            for rxcui in target.keys() | drugs.keys()
        ]
        changed = [difference for difference in differences if difference]
        all_drugs[formulary_id] = fmean(differences)
        changed_drugs[formulary_id] = fmean(changed) if changed else math.nan
    return all_drugs, changed_drugs
