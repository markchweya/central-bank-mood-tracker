"""Choose which paragraphs to score.

Scoring all ~620k paragraphs on a CPU-only laptop would take weeks, so the
index is built from a fixed-size random sample per country and month,
drawn only from paragraphs that talk about the economy or monetary policy.
"""

from __future__ import annotations

import re

import pandas as pd

RELEVANT = re.compile(
    r"inflation|interest rate|policy rate|monetary policy|price stability|"
    r"\bgrowth\b|\beconom(?:y|ies|ic)\b|recession|unemployment|labou?r market|"
    r"\bdemand\b|\bGDP\b|\boutput gap\b|\bwages?\b|\bprices\b",
    re.IGNORECASE,
)

# Bibliography entries and footnotes that survive the PDF conversion.
REFERENCE = re.compile(
    r"^\s*(?:-\s*)?\[\d+\]|working paper|\bdoi\b|https?://|\bpp\.\s*\d|\(\d{4}\),\s*['\"‘“]",
    re.IGNORECASE,
)


def relevant_paragraphs(paragraphs: pd.DataFrame) -> pd.DataFrame:
    text = paragraphs["paragraph"]
    keep = text.str.contains(RELEVANT) & ~text.str.contains(REFERENCE)
    return paragraphs[keep]


def sample_paragraphs(
    paragraphs: pd.DataFrame,
    countries: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    per_month: int = 5,
    seed: int = 0,
) -> pd.DataFrame:
    """Draw up to `per_month` relevant paragraphs per country and month.

    The draw is deterministic for a given seed, and a larger `per_month` keeps
    every paragraph a smaller one picked, so scores can be topped up later.
    """
    selected = paragraphs[paragraphs["country"].notna()]
    if countries:
        selected = selected[selected["country"].isin(countries)]
    if start:
        selected = selected[selected["date"] >= pd.Timestamp(start)]
    if end:
        selected = selected[selected["date"] <= pd.Timestamp(end)]
    selected = relevant_paragraphs(selected)

    month = selected["date"].dt.to_period("M")
    rank = (
        selected.sample(frac=1.0, random_state=seed)
        .groupby([selected["country"], month])
        .cumcount()
    )
    sampled = selected.loc[rank[rank < per_month].index]
    return sampled.assign(month=month.loc[sampled.index]).sort_values(["country", "date"])
