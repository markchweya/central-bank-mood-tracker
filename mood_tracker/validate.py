"""Check the LLM's labels against hand labels.

Step 1, export a labelling sheet (open it in Excel, fill the stance and
outlook columns, save as CSV):

    python -m mood_tracker.validate export --n 200

Step 2, score the same paragraphs with a backend and report agreement:

    python -m mood_tracker.validate evaluate data/validation/to_label.csv

`evaluate` also saves the hand labels (ids and labels only, no speech text) to
validation/labels.csv, which is small enough to commit, so others can
re-run the check against the same ground truth.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from mood_tracker.sampling import relevant_paragraphs
from mood_tracker.sentiment import (
    OUTLOOK_LABELS, PROMPT_VERSION, STANCE_LABELS, Label, make_scorer,
)

ROOT = Path(__file__).resolve().parents[1]
PARAGRAPHS = ROOT / "data" / "processed" / "paragraphs.parquet"
SHEET = ROOT / "data" / "validation" / "to_label.csv"
COMMITTED_LABELS = ROOT / "validation" / "labels.csv"
KEY = ["speech_id", "paragraph_no"]
DIMENSIONS = {"stance": STANCE_LABELS, "outlook": OUTLOOK_LABELS}
DEV_SIZE = 60


def export_sheet(n: int, seed: int) -> None:
    paragraphs = pd.read_parquet(PARAGRAPHS)
    pool = relevant_paragraphs(paragraphs[paragraphs["country"].notna()])
    # Spread the sheet across countries so no single central bank dominates it.
    per_country = max(1, n // pool["country"].nunique())
    shuffled = pool.sample(frac=1.0, random_state=seed)
    sheet = shuffled.groupby("country").head(per_country).head(n)
    sheet = sheet[KEY + ["country", "date", "paragraph"]].assign(stance="", outlook="")
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    sheet.to_csv(SHEET, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(sheet)} paragraphs to {SHEET}")
    print("Fill in stance (" + "/".join(STANCE_LABELS) + ") and outlook ("
          + "/".join(OUTLOOK_LABELS) + "), then run `evaluate`.")


def agreement_report(truth: pd.Series, predicted: pd.Series, labels: tuple[str, ...]) -> str:
    accuracy = (truth == predicted).mean()
    f1_scores = []
    for label in labels:
        tp = ((truth == label) & (predicted == label)).sum()
        fp = ((truth != label) & (predicted == label)).sum()
        fn = ((truth == label) & (predicted != label)).sum()
        if tp + fp + fn:
            f1_scores.append(2 * tp / (2 * tp + fp + fn))
    macro_f1 = sum(f1_scores) / len(f1_scores)
    confusion = pd.crosstab(truth.rename("reference"), predicted.rename("model"))
    return f"accuracy {accuracy:.0%}, macro-F1 {macro_f1:.2f}\n{confusion.to_string()}"


def select_split(sheet: pd.DataFrame, split: str) -> pd.DataFrame:
    """The sheet is already shuffled; its first DEV_SIZE rows are for prompt tuning.

    Tune prompts on `dev` only and report `test`, so the accuracy we quote was
    never used to choose the prompt.
    """
    if split == "dev":
        return sheet.iloc[:DEV_SIZE]
    if split == "test":
        return sheet.iloc[DEV_SIZE:]
    return sheet


# Stands in for a paragraph the model gave no valid label for, so it counts as wrong.
FAILED = Label("failed", "failed")


def score_or_fail(scorer, text: str) -> Label:
    try:
        return scorer.score(text)
    except (ValueError, KeyError):
        return FAILED


def evaluate(sheet_path: Path, backend: str, model: str | None, split: str = "all") -> None:
    sheet = pd.read_csv(sheet_path, encoding="utf-8-sig")
    for column, labels in DIMENSIONS.items():
        sheet[column] = sheet[column].astype(str).str.strip().str.lower()
        sheet = sheet[sheet[column].isin(labels)]
    if sheet.empty:
        raise SystemExit("No labelled rows found; fill in the stance and outlook columns first.")

    COMMITTED_LABELS.parent.mkdir(parents=True, exist_ok=True)
    # Optional `labeller` column records who made the reference labels (a person or a model).
    keep = KEY + ["country", "stance", "outlook"] + (["labeller"] if "labeller" in sheet else [])
    sheet[keep].to_csv(COMMITTED_LABELS, index=False)

    sheet = select_split(sheet, split)
    scorer = make_scorer(backend, model)
    predictions = [score_or_fail(scorer, text) for text in sheet["paragraph"]]
    failed = sum(p is FAILED for p in predictions)
    print(f"{scorer.backend} / {scorer.model}, prompt {PROMPT_VERSION}, {split} split: "
          f"{len(sheet)} reference-labelled paragraphs"
          + (f", {failed} with no valid reply (counted as wrong)" if failed else "") + "\n")
    for column, labels in DIMENSIONS.items():
        predicted = pd.Series([getattr(p, column) for p in predictions], index=sheet.index)
        sheet[f"model_{column}"] = predicted
        print(f"{column}: {agreement_report(sheet[column], predicted, labels)}\n")

    # Keep row-level predictions for error analysis (contains speech text, so not committed).
    safe_model = scorer.model.replace(":", "-").replace("/", "-")
    out = SHEET.parent / f"predictions__{safe_model}__{PROMPT_VERSION}__{split}.csv"
    sheet.to_csv(out, index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="write a labelling sheet")
    export.add_argument("--n", type=int, default=200)
    export.add_argument("--seed", type=int, default=42)
    check = commands.add_parser("evaluate", help="compare a backend with hand labels")
    check.add_argument("sheet", type=Path, nargs="?", default=SHEET)
    check.add_argument("--backend", choices=["ollama", "claude"], default="ollama")
    check.add_argument("--model")
    check.add_argument("--split", choices=["all", "dev", "test"], default="all",
                       help=f"dev = first {DEV_SIZE} rows (for tuning), test = the rest")
    args = parser.parse_args()

    if args.command == "export":
        export_sheet(args.n, args.seed)
    else:
        evaluate(args.sheet, args.backend, args.model, args.split)


if __name__ == "__main__":
    main()
