"""Score a sample of speech paragraphs and save the labels.

Results go to data/scores/<backend>__<model>__<prompt version>.parquet. The run is resumable:
paragraphs already in that file are skipped, and progress is saved every
`--save-every` paragraphs, so you can stop with Ctrl+C and pick up later.

Examples:
    # Quick pilot: 5 countries, 2 paragraphs per month since 2020
    python -m mood_tracker.score --countries US EA GB JP KE --start 2020 --per-month 2

    # Optional Claude backend
    python -m mood_tracker.score --backend claude --countries KE --per-month 5
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from mood_tracker.sampling import sample_paragraphs
from mood_tracker.sentiment import PROMPT_VERSION, make_scorer

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PARAGRAPHS = DATA_DIR / "processed" / "paragraphs.parquet"
SCORES_DIR = DATA_DIR / "scores"
KEY = ["speech_id", "paragraph_no"]


def scores_path(backend: str, model: str) -> Path:
    # One file per backend, model and prompt version, so labels from different
    # prompts are never mixed when resuming a run.
    safe_model = model.replace(":", "-").replace("/", "-")
    return SCORES_DIR / f"{backend}__{safe_model}__{PROMPT_VERSION}.parquet"


def load_existing(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame(columns=KEY + ["country", "date", "stance", "outlook", "scored_at"])


def save(existing: pd.DataFrame, new_rows: list[dict], path: Path) -> pd.DataFrame:
    combined = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path, index=False)
    return combined


def run(args: argparse.Namespace) -> None:
    scorer = make_scorer(args.backend, args.model)
    path = scores_path(scorer.backend, scorer.model)
    existing = load_existing(path)

    sample = sample_paragraphs(
        pd.read_parquet(PARAGRAPHS),
        countries=args.countries,
        start=args.start,
        end=args.end,
        per_month=args.per_month,
        seed=args.seed,
    )
    done = existing.set_index(KEY).index
    todo = sample[~sample.set_index(KEY).index.isin(done)]
    if args.limit:
        todo = todo.head(args.limit)
    print(f"{len(sample):,} paragraphs in sample, {len(sample) - len(todo):,} already scored, "
          f"{len(todo):,} to go -> {path.name}")

    new_rows: list[dict] = []
    started = time.time()
    try:
        for i, row in enumerate(todo.itertuples(index=False), start=1):
            try:
                label = scorer.score(row.paragraph)
            except (ValueError, KeyError) as error:
                print(f"  skipped {row.speech_id}#{row.paragraph_no}: {error}")
                continue
            new_rows.append({
                "speech_id": row.speech_id, "paragraph_no": row.paragraph_no,
                "country": row.country, "date": row.date,
                "stance": label.stance, "outlook": label.outlook,
                "scored_at": pd.Timestamp.now(),
            })
            if i % args.save_every == 0 or i == len(todo):
                existing = save(existing, new_rows, path)
                new_rows = []
                rate = (time.time() - started) / i
                remaining_hours = rate * (len(todo) - i) / 3600
                print(f"  {i:,}/{len(todo):,} scored, {rate:.1f}s each, ~{remaining_hours:.1f}h left")
    except KeyboardInterrupt:
        print("Stopped; saving progress.")
    finally:
        if new_rows:
            save(existing, new_rows, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score speech paragraphs with an LLM.")
    parser.add_argument("--backend", choices=["ollama", "claude"], default="ollama")
    parser.add_argument("--model", help="model name (default: llama3.2:3b for ollama)")
    parser.add_argument("--countries", nargs="+", help="ISO codes, e.g. US EA GB KE")
    parser.add_argument("--start", help="first date, e.g. 2005 or 2005-01-01")
    parser.add_argument("--end", help="last date")
    parser.add_argument("--per-month", type=int, default=5, help="paragraphs per country-month")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--limit", type=int, help="score at most this many in this run")
    parser.add_argument("--save-every", type=int, default=25)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
