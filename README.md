# Central Bank Mood Tracker

An AI that reads central bank speeches, measures how central bankers sound, and tests whether that tone helps forecast the economy.

It extends the method in the BIS paper [*Large language models: a primer for economists*](https://www.bis.org/publ/qtrpdf/r_qt2412b.htm) (Kwon, Park, Perez-Cruz and Rungcharoenkitkul, 2024). The paper's [sample code](https://github.com/bis-med-it/LLM_Primer_for_Economists) shows the pipeline on arXiv abstracts with placeholder sentiment. This project runs it on real economic text, with real LLM scoring, and evaluates the result against macro data.

## How it works

1. **Speeches.** The BIS archive of central bankers' speeches: about 21,000 speeches from 1996 onwards, matched to their central bank and country.
2. **Sentiment.** An LLM rates each paragraph on monetary-policy stance (hawkish/dovish) and growth outlook. By default it runs locally through [Ollama](https://ollama.com); an API backend is optional.
3. **Topics.** BERTopic groups paragraphs into themes such as inflation, labour markets and financial stability.
4. **Mood index.** Paragraph scores are aggregated into a monthly index per country by a COBOL batch job, the way bank back-office systems still process records.
5. **Forecast test.** In R, the standard econometrics language at central banks: does the index improve forecasts of GDP growth and policy-rate changes beyond standard benchmarks?
6. **Dashboard.** Explore the index by country and topic, and score a speech of your own.

## Languages

| Language | Used for | Why |
| --- | --- | --- |
| Python | Data loading, LLM scoring, topics | The BIS paper's own toolchain |
| COBOL | Monthly mood index batch job | Still runs core banking batch processing |
| R | Forecast evaluation | Standard for applied econometrics at central banks |

## Status

| Step | Status |
| --- | --- |
| Speech loader | done |
| LLM sentiment scoring | done; checked against 200 reference labels |
| Topic modelling | planned |
| Monthly mood index | done (COBOL) |
| Macro data and forecast test | planned |
| Dashboard | planned |

## Run it locally

Requires Python 3.10+.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m mood_tracker.download        # fetches the BIS archive (~130 MB) into data/raw/
python -m mood_tracker.load_speeches   # writes data/processed/*.parquet
```

### Score sentiment

Install [Ollama](https://ollama.com) and pull a model. `gemma4:latest` with prompt v3 is the most accurate local option we tested (84% stance, 73% outlook on held-out paragraphs, see [results/labeller_accuracy.md](results/labeller_accuracy.md)); `llama3.2:3b` is the default because it is smaller and a little faster. On a laptop CPU a paragraph takes about 7-12 seconds, so scoring works on a sample per country and month:

```bash
ollama pull gemma4:latest
# pilot: US and Kenya, 2 paragraphs per month since 2023
python -m mood_tracker.score --model gemma4:latest --countries US KE --start 2023 --per-month 2
```

Runs are resumable: stop with Ctrl+C and the same command carries on. To use Claude instead, `pip install anthropic`, sign in with an API key, and add `--backend claude`.

### Check accuracy

```bash
python -m mood_tracker.validate export --n 200     # writes a sheet to label by hand
python -m mood_tracker.validate evaluate --model gemma4:latest --split dev   # tune on the first 60 rows
python -m mood_tracker.validate evaluate --model gemma4:latest --split test  # report on the rest
```

### Build the mood index (COBOL)

The index is built by [`cobol/MOODIDX.cbl`](cobol/MOODIDX.cbl), a fixed-format COBOL batch job. It validates each scored paragraph, sorts by country and month, and does a two-level control break to write one line per country-month:

- **stance index** = (hawkish - dovish) / paragraphs with a stance label, from -1 (dovish) to +1 (hawkish)
- **outlook index** = (positive - negative) / paragraphs with an outlook label, from -1 (gloomy) to +1 (upbeat)

It also prints a summary report per country. Install [GnuCOBOL](https://gnucobol.sourceforge.io) 3.x:

- **Windows:** in an [MSYS2](https://www.msys2.org) shell, run `pacman -S mingw-w64-ucrt-x86_64-gnucobol`
- **macOS:** `brew install gnucobol`
- **Debian/Ubuntu:** `sudo apt install gnucobol`

Then:

```bash
python -m mood_tracker.mood_index    # compiles MOODIDX if needed, runs it, writes data/index/
```

Tests check the COBOL output against an independent pandas calculation:

```bash
pip install -r requirements-dev.txt
pytest
```

## Data

Speeches come from the [BIS central bankers' speeches](https://www.bis.org/cbspeeches/) archive and remain subject to the BIS terms of use. Downloaded data is not committed to this repository.
