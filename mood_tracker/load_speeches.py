"""Load the BIS central bankers' speeches archive into clean tables.

Reads data/raw/speeches.zip (fetch it with `python -m mood_tracker.download`)
and writes two Parquet files to data/processed/:

- speeches.parquet   one row per speech, with the speaking institution and country
- paragraphs.parquet one row per paragraph, the unit the sentiment model scores

Usage:
    python -m mood_tracker.load_speeches
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_ZIP = DATA_DIR / "raw" / "speeches.zip"
OUT_DIR = DATA_DIR / "processed"

# Paragraphs shorter than this are headings, sign-offs or footnote markers.
MIN_PARAGRAPH_CHARS = 200

INSTITUTION_PATTERN = re.compile(
    r"(?:of|at) (?:the )?"
    r"((?:[A-Z][\w'’]+ )*"
    r"(?:Bank|Reserve|Bundesbank|Authority|Riksbank|Nationalbank|Banque|Banco|Banca)"
    r"(?: of(?: the)?(?: [A-Z][\w’]+)+)?)"
)

# Institution name as written in the speech description -> ISO 3166 alpha-2 code.
# "EA" marks the euro area. Covers the banks with the most speeches; extend as needed.
INSTITUTION_COUNTRY = {
    "European Central Bank": "EA",
    "Federal Reserve": "US",
    "US Federal Reserve": "US",
    "Federal Reserve Bank of New York": "US",
    "Reserve Bank of India": "IN",
    "Deutsche Bundesbank": "DE",
    "Bank of England": "GB",
    "Bank of Japan": "JP",
    "Bank of Canada": "CA",
    "Reserve Bank of Australia": "AU",
    "Central Bank of Malaysia": "MY",
    "Sveriges Riksbank": "SE",
    "Bank of Italy": "IT",
    "Bank of France": "FR",
    "South African Reserve Bank": "ZA",
    "Swiss National Bank": "CH",
    "Central Bank of Ireland": "IE",
    "Bank of Spain": "ES",
    "Monetary Authority of Singapore": "SG",
    "Bank of Albania": "AL",
    "Hong Kong Monetary Authority": "HK",
    "Norges Bank": "NO",
    "Bank of Thailand": "TH",
    "Bank of Finland": "FI",
    "Netherlands Bank": "NL",
    "Reserve Bank of New Zealand": "NZ",
    "Bank of Greece": "GR",
    "Central Bank of Kenya": "KE",
    "Bank of Mauritius": "MU",
    "Bank of Zambia": "ZM",
    "National Bank of Serbia": "RS",
    "Bank of Uganda": "UG",
    "Central Bank of Chile": "CL",
    "State Bank of Pakistan": "PK",
    "Reserve Bank of Fiji": "FJ",
    "People's Bank of China": "CN",
    "Central Bank of Barbados": "BB",
    "Central Bank of the Philippines": "PH",
    "Bank of Israel": "IL",
    "National Bank of Denmark": "DK",
    "Bank of Korea": "KR",
    "Bank of Mexico": "MX",
}


def read_raw(path: Path = RAW_ZIP) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        with archive.open("speeches.csv") as csv_file:
            return pd.read_csv(csv_file)


def clean_speeches(raw: pd.DataFrame) -> pd.DataFrame:
    speeches = raw.rename(columns={"author": "speaker"}).copy()
    speeches["date"] = pd.to_datetime(speeches["date"], errors="coerce")
    # The archive has a few dates typed in the future; drop them with the unparseable ones.
    speeches = speeches[speeches["date"].notna() & (speeches["date"] <= pd.Timestamp.today())]
    speeches = speeches.dropna(subset=["text"]).drop_duplicates(subset="url")

    speeches["institution"] = speeches["description"].str.extract(INSTITUTION_PATTERN)[0]
    speeches["country"] = speeches["institution"].map(INSTITUTION_COUNTRY)
    # The last URL segment is the BIS id: review/r230320b.pdf, review/r131024b.htm,
    # or speeches/20260817-ai-and-monetary-policy for the newest ones.
    speeches["speech_id"] = speeches["url"].str.extract(r"/([^/]+?)(?:\.pdf|\.htm)?$")[0]
    if speeches["speech_id"].isna().any() or speeches["speech_id"].duplicated().any():
        raise ValueError("Speech URLs no longer give a unique id; update the speech_id pattern")
    speeches["n_chars"] = speeches["text"].str.len()

    columns = ["speech_id", "date", "speaker", "institution", "country",
               "title", "description", "url", "n_chars", "text"]
    return speeches[columns].sort_values("date").reset_index(drop=True)


def split_paragraphs(speeches: pd.DataFrame) -> pd.DataFrame:
    paragraphs = (
        speeches[["speech_id", "date", "country", "text"]]
        .assign(paragraph=lambda df: df["text"].str.split(r"\n\s*\n"))
        .drop(columns="text")
        .explode("paragraph")
    )
    paragraphs["paragraph"] = paragraphs["paragraph"].str.strip()
    paragraphs = paragraphs[paragraphs["paragraph"].str.len() >= MIN_PARAGRAPH_CHARS]
    # Markdown headings carried over from the PDF conversion are not speech content.
    paragraphs = paragraphs[~paragraphs["paragraph"].str.startswith("#")]
    paragraphs["paragraph_no"] = paragraphs.groupby("speech_id").cumcount()
    return paragraphs.reset_index(drop=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    speeches = clean_speeches(read_raw())
    paragraphs = split_paragraphs(speeches)
    speeches.to_parquet(OUT_DIR / "speeches.parquet", index=False)
    paragraphs.to_parquet(OUT_DIR / "paragraphs.parquet", index=False)

    matched = speeches["country"].notna().mean()
    print(f"{len(speeches):,} speeches, {speeches['date'].min():%Y-%m} to {speeches['date'].max():%Y-%m}")
    print(f"{matched:.0%} mapped to a country; {len(paragraphs):,} paragraphs")


if __name__ == "__main__":
    main()
