<<<<<<< HEAD
# AI Code Explanation Notebook

Streamlit app for using an approved AI assistant to explain, improve, test and document small Python programs.
The assistant is a **local mock by default** (works offline); the Claude API is an optional toggle with automatic mock fallback.

## Run
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed_data.py            # optional: 40 demo entries + sample CSV/JSON in data/
streamlit run app.py
python -m pytest tests         # run tests
```

## Demo script (matches the brief)
1. **Home**: branded welcome, stats, warning banner.
2. **New Entry**: type a 1-char title or broken code to show validation, fix it, click *Explain & Suggest* → *Run Tests* → *Save*.
3. **Dashboard**: metrics, Matplotlib charts, category table, threshold warnings.
4. Stop and relaunch `streamlit run app.py`: entries persist (`data/entries.json`, mirrored to `entries.csv`).
5. **Import / Export**: upload `data/sample_import_with_errors.csv` (shows row-level errors), then download Markdown / TXT / CSV / chart PNGs.

## Layout
`core/` models, validation, storage, ai_assistant, analyzer, sandbox, search, summary, charts, exporter, importer · `app.py` UI · `seed_data.py` · `tests/`

## Notes
- Sandbox: static checks block risky imports/calls (os, subprocess, socket, eval, exec, open…), then run in a subprocess with a 5 s timeout and capped output. It is a safeguard for demo use, not a hardened security boundary.
- Corrupted/missing `entries.json` is backed up and replaced with a clean template.
- Optional API mode: `pip install anthropic`, set `ANTHROPIC_API_KEY` or paste a key in the sidebar.
=======
# AI-Code-Explanation-Notebook
>>>>>>> 72d6c294a229a6e0c984fc790418c2258f8330d5
