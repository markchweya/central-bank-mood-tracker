"""Build the monthly mood index by running the COBOL batch job.

Python only moves data in and out: it writes the scored paragraphs as
fixed-width records, compiles cobol/MOODIDX.cbl with GnuCOBOL if needed,
runs it, and reads the fixed-width index it produces.

    python -m mood_tracker.mood_index                      # default scores file
    python -m mood_tracker.mood_index --scores data/scores/claude__claude-opus-5-5.parquet

Outputs, in data/index/:
    scores.dat        input records handed to COBOL
    mood_index.dat    COBOL output, one line per country-month
    mood_report.txt   COBOL summary report
    mood_index.csv    the same index as a table, with NaN where a month had no labels
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COBOL_SOURCE = ROOT / "cobol" / "MOODIDX.cbl"
BUILD_DIR = ROOT / "build"
INDEX_DIR = ROOT / "data" / "index"
DEFAULT_SCORES = ROOT / "data" / "scores" / "ollama__llama3.2-3b.parquet"
EXE_NAME = "moodidx.exe" if os.name == "nt" else "moodidx"

INDEX_COLUMNS = ["country", "month", "n_paragraphs", "n_stance", "stance_index",
                 "n_outlook", "outlook_index"]
INDEX_WIDTHS = [2, 8, 6, 6, 8, 6, 8]  # each field plus its leading separator


def find_cobc() -> Path:
    for candidate in (os.environ.get("COBC"), shutil.which("cobc"),
                      "C:/msys64/ucrt64/bin/cobc.exe", "C:/msys64/mingw64/bin/cobc.exe"):
        if candidate and Path(candidate).exists():
            return Path(candidate)
    raise SystemExit("GnuCOBOL not found. Install it (see README) or set COBC to the cobc path.")


def cobol_env(cobc: Path) -> dict[str, str]:
    """Environment for cobc and the compiled job, including MSYS2 builds on Windows."""
    env = dict(os.environ)
    bin_dir = cobc.parent
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    share = bin_dir.parent / "share" / "gnucobol"
    if share.exists():
        env.setdefault("COB_CONFIG_DIR", str(share / "config"))
        env.setdefault("COB_COPY_DIR", str(share / "copy"))
    lib = bin_dir.parent / "lib" / "gnucobol"
    if lib.exists():
        env.setdefault("COB_LIBRARY_PATH", str(lib))
    return env


def build(cobc: Path, env: dict[str, str]) -> Path:
    exe = BUILD_DIR / EXE_NAME
    if exe.exists() and exe.stat().st_mtime >= COBOL_SOURCE.stat().st_mtime:
        return exe
    BUILD_DIR.mkdir(exist_ok=True)
    subprocess.run([str(cobc), "-x", "-Wall", str(COBOL_SOURCE), "-o", str(exe)],
                   env=env, check=True)
    return exe


def write_records(scores: pd.DataFrame, path: Path) -> int:
    scores = scores.dropna(subset=["country", "date", "stance", "outlook"])
    month = pd.to_datetime(scores["date"]).dt.strftime("%Y-%m")
    lines = (scores["country"].str.ljust(2) + " " + month + " "
             + scores["stance"].str.ljust(8) + " " + scores["outlook"].str.ljust(8))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return len(lines)


def read_index(path: Path) -> pd.DataFrame:
    index = pd.read_fwf(path, widths=INDEX_WIDTHS, names=INDEX_COLUMNS,
                        dtype={"country": str, "month": str})
    # COBOL writes 0 when a month had no labelled paragraphs; mark those as missing.
    index.loc[index["n_stance"] == 0, "stance_index"] = float("nan")
    index.loc[index["n_outlook"] == 0, "outlook_index"] = float("nan")
    return index


def run(scores_path: Path) -> pd.DataFrame:
    cobc = find_cobc()
    env = cobol_env(cobc)
    exe = build(cobc, env)

    records = INDEX_DIR / "scores.dat"
    index_file = INDEX_DIR / "mood_index.dat"
    report_file = INDEX_DIR / "mood_report.txt"
    written = write_records(pd.read_parquet(scores_path), records)
    print(f"Wrote {written:,} records from {scores_path.name}")

    env.update(DD_SCORESIN=str(records), DD_INDEXOUT=str(index_file),
               DD_REPORTOUT=str(report_file))
    job = subprocess.run([str(exe)], env=env)
    # Return code 4 means some records were rejected; 8 or more is a failure.
    if job.returncode >= 8:
        raise SystemExit(f"MOODIDX failed with return code {job.returncode}")

    index = read_index(index_file)
    index.to_csv(INDEX_DIR / "mood_index.csv", index=False)
    print(report_file.read_text())
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the monthly mood index with COBOL.")
    parser.add_argument("--scores", type=Path, default=DEFAULT_SCORES)
    args = parser.parse_args()
    if not args.scores.exists():
        sys.exit(f"No scores at {args.scores}; run `python -m mood_tracker.score` first.")
    run(args.scores)


if __name__ == "__main__":
    main()
