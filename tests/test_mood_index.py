"""Check the COBOL mood index against an independent pandas calculation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mood_tracker import mood_index
from mood_tracker.sentiment import OUTLOOK_SCORE, STANCE_SCORE


def synthetic_scores(n: int = 2000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "country": rng.choice(["US", "EA", "KE", "GB"], n),
        "date": pd.Timestamp("2015-01-01") + pd.to_timedelta(rng.integers(0, 3650, n), unit="D"),
        "stance": rng.choice(["hawkish", "dovish", "neutral", "none"], n),
        "outlook": rng.choice(["positive", "negative", "neutral", "none"], n),
    })


def reference_index(scores: pd.DataFrame) -> pd.DataFrame:
    frame = scores.assign(
        month=pd.to_datetime(scores["date"]).dt.strftime("%Y-%m"),
        stance_value=scores["stance"].map(STANCE_SCORE),
        outlook_value=scores["outlook"].map(OUTLOOK_SCORE),
    )
    grouped = frame.groupby(["country", "month"])
    return pd.DataFrame({
        "n_paragraphs": grouped.size(),
        "stance_index": grouped["stance_value"].mean(),
        "outlook_index": grouped["outlook_value"].mean(),
    }).reset_index()


@pytest.fixture(scope="module")
def cobol_ready():
    try:
        cobc = mood_index.find_cobc()
    except SystemExit:
        pytest.skip("GnuCOBOL is not installed")
    env = mood_index.cobol_env(cobc)
    return mood_index.build(cobc, env), env


def test_cobol_matches_pandas(tmp_path, monkeypatch, cobol_ready):
    monkeypatch.setattr(mood_index, "INDEX_DIR", tmp_path)
    scores = synthetic_scores()
    scores_file = tmp_path / "scores.parquet"
    scores.to_parquet(scores_file)

    cobol = mood_index.run(scores_file)
    expected = reference_index(scores)

    merged = cobol.merge(expected, on=["country", "month"], suffixes=("", "_ref"))
    assert len(merged) == len(expected) == len(cobol)
    assert (merged["n_paragraphs"] == merged["n_paragraphs_ref"]).all()
    # COBOL rounds to 4 decimals.
    np.testing.assert_allclose(merged["stance_index"], merged["stance_index_ref"], atol=5e-5)
    np.testing.assert_allclose(merged["outlook_index"], merged["outlook_index_ref"], atol=5e-5)


def test_bad_records_are_rejected_not_counted(tmp_path, monkeypatch, cobol_ready):
    monkeypatch.setattr(mood_index, "INDEX_DIR", tmp_path)
    scores = pd.DataFrame({
        "country": ["KE", "KE", "KE"],
        "date": pd.to_datetime(["2024-03-01", "2024-03-15", "2024-03-20"]),
        "stance": ["hawkish", "dovish", "sideways"],
        "outlook": ["positive", "positive", "positive"],
    })
    scores_file = tmp_path / "scores.parquet"
    scores.to_parquet(scores_file)

    index = mood_index.run(scores_file)

    assert index.to_dict("records") == [{
        "country": "KE", "month": "2024-03", "n_paragraphs": 2, "n_stance": 2,
        "stance_index": 0.0, "n_outlook": 2, "outlook_index": 1.0,
    }]
