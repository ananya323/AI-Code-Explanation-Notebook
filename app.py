"""AI Code Explanation Notebook — Streamlit app.  Run: streamlit run app.py"""
from datetime import date, datetime

import pandas as pd
import streamlit as st

import seed_data
from core import charts, exporter, importer, search, storage, summary
from core.ai_assistant import suggest
from core.analyzer import diff_code, evaluate
from core.models import CATEGORIES, DIFFICULTIES, STATUSES, NotebookEntry
from core.validation import parse_tags, validate_code, validate_fields, validate_title

st.set_page_config(page_title="AI Code Explanation Notebook", page_icon="📓", layout="wide")
ss = st.session_state

DEFAULT_CODE = ("def evens(nums):\n    result = []\n    for n in nums:\n        if n % 2 == 0:\n"
                "            result.append(n)\n    return result\n\nprint(evens(range(10)))\n")
STATUS_ICON = {"passed": "✅ passed", "failed": "❌ failed", "timeout": "⏱️ timeout", "blocked": "🚫 blocked"}

# ---------------------------------------------------------------- sidebar
st.sidebar.title("📓 Code Notebook")
st.sidebar.caption("AI Code Explanation Notebook")
PAGE = st.sidebar.radio("Navigate", ["Home", "New Entry", "Browse & Search", "Dashboard", "Import / Export"])
st.sidebar.divider()
st.sidebar.subheader("AI assistant")
ss.setdefault("use_api", False)
st.sidebar.toggle("Use Claude API (optional)", key="use_api",
                  help="Off = local mock assistant (works offline). On = Claude API, falling back to the mock on any error.")
if ss.use_api:
    st.sidebar.text_input("API key", type="password", key="api_key", help="Or set ANTHROPIC_API_KEY.")
st.sidebar.subheader("Warning thresholds")
STALE_DAYS = st.sidebar.slider("Draft is stale after (days)", 1, 30, 7)
MAX_CX = st.sidebar.slider("Max complexity", 3, 20, 8)

entries, notice = storage.load_entries()
if notice:
    st.sidebar.warning(notice)


def persist(new_entries):
    storage.save_entries(new_entries)


def results_panel(entry: NotebookEntry):
    c1, c2 = st.columns(2)
    for col, which, label in ((c1, "original", "Original"), (c2, "improved", "Improved")):
        res = getattr(entry, f"test_{which}")
        with col:
            st.markdown(f"**{label}:** {STATUS_ICON.get(res.get('status'), 'not run')}"
                        + (f" · {res.get('runtime_ms')} ms" if res else ""))
            if res.get("stdout"):
                st.code(res["stdout"], language="text")
            if res.get("stderr"):
                st.code(res["stderr"], language="text")
    m = pd.DataFrame({"Original": entry.metrics_before, "Improved": entry.metrics_after})
    st.dataframe(m.rename(index={"lines": "Lines of code", "functions": "Functions",
                                 "complexity": "Complexity", "docstring_coverage": "Docstring coverage %",
                                 "valid": "Valid syntax"}).astype(str), use_container_width=True)
    st.metric("Improvement score", f"{entry.score} / 100")


def entry_table(es) -> pd.DataFrame:
    return pd.DataFrame([{
        "ID": e.id, "Title": e.title, "Category": e.category, "Difficulty": e.difficulty,
        "Status": e.status, "Score": e.score, "Tests (orig→impr)":
            f"{(e.test_original or {}).get('status', '-')} → {(e.test_improved or {}).get('status', '-')}",
        "Created": e.created_at[:16].replace("T", " ")} for e in es])


def show_warnings(ws, limit=8):
    if not ws:
        st.success("No threshold warnings.")
        return
    st.warning(f"{len(ws)} warning(s) need attention.")
    with st.expander("Show warnings", expanded=False):
        for w in ws[:limit * 3]:
            (st.error if w["level"] == "error" else st.warning)(w["message"])


# ---------------------------------------------------------------- Home
if PAGE == "Home":
    st.title("📓 AI Code Explanation Notebook")
    st.caption("Use an approved AI assistant to explain, improve, test and document small Python programs. "
               "All data is stored locally in `data/entries.json`.")
    s = summary.compute_summary(entries)
    a, b, c, d = st.columns(4)
    a.metric("Entries", s["total"])
    b.metric("Documented", s["by_status"]["Documented"])
    c.metric("Avg improvement score", s["avg_score"])
    d.metric("Improved code passing", f"{s['pass_rate_improved']}%" if s["pass_rate_improved"] is not None else "–")
    show_warnings(summary.get_warnings(entries, STALE_DAYS, MAX_CX))
    if not entries:
        st.info("No entries yet. Create one under **New Entry**, or load 40 demo entries.")
        if st.button("Load demo data"):
            seed_data.seed()
            st.rerun()
    else:
        st.subheader("Most recent entries")
        st.dataframe(entry_table(sorted(entries, key=lambda e: e.created_at, reverse=True)[:5]),
                     use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- New entry
elif PAGE == "New Entry":
    st.title("New Entry")
    for k, v in {"ne_title": "", "ne_category": CATEGORIES[0], "ne_difficulty": "Easy", "ne_tags": "",
                 "ne_code": DEFAULT_CODE, "ne_status": "Draft", "ne_explanation": "", "ne_improved": "",
                 "ne_rationale": "", "ne_source": "", "ne_ran": False, "ne_errors": [], "ne_results": None,
                 "ne_msg": ""}.items():
        ss.setdefault(k, v)

    def build_entry():
        return NotebookEntry(title=ss.ne_title.strip() or "Untitled", category=ss.ne_category, code=ss.ne_code,
                             difficulty=ss.ne_difficulty, explanation=ss.ne_explanation,
                             improved_code=ss.ne_improved, rationale=ss.ne_rationale, status=ss.ne_status,
                             tags=parse_tags(ss.ne_tags), source=ss.ne_source or "manual")

    def do_suggest():
        errs = validate_code(ss.ne_code)
        ss.ne_errors = errs
        if errs:
            return
        res = suggest(ss.ne_code, ss.ne_category, ss.use_api, ss.get("api_key", ""))
        ss.ne_explanation, ss.ne_improved = res["explanation"], res["improved_code"]
        ss.ne_rationale, ss.ne_source = res["rationale"], res["source"]
        ss.ne_ran, ss.ne_results = False, None

    def do_tests():
        errs = validate_code(ss.ne_code)
        if ss.ne_improved.strip():
            errs += validate_code(ss.ne_improved, "Improved code")
        ss.ne_errors = errs
        if errs:
            return
        e = evaluate(build_entry(), run_tests=True)
        ss.ne_results, ss.ne_ran = e.to_dict(), True
        if ss.ne_status == "Draft" and e.passed("improved"):
            ss.ne_status = "Tested"

    def do_save():
        errs = validate_fields(ss.ne_title, ss.ne_category, ss.ne_difficulty, ss.ne_status, ss.ne_code,
                               improved_code=ss.ne_improved)
        ss.ne_errors = errs
        if errs:
            return
        e = evaluate(build_entry(), run_tests=ss.ne_ran)
        current, _ = storage.load_entries()
        persist(current + [e])
        ss.ne_msg = f"Saved “{e.title}” (id {e.id}, score {e.score})."
        ss.update(ne_title="", ne_tags="", ne_code=DEFAULT_CODE, ne_status="Draft", ne_explanation="",
                  ne_improved="", ne_rationale="", ne_source="", ne_ran=False, ne_results=None, ne_errors=[])

    if ss.ne_msg:
        st.success(ss.ne_msg)
        ss.ne_msg = ""
    left, right = st.columns([3, 2])
    with left:
        st.text_input("Title", key="ne_title", placeholder="e.g. Filter even numbers")
        if ss.ne_title and (t_err := validate_title(ss.ne_title)):
            st.caption(f":red[{t_err[0]}]")
        st.text_area("Python code", key="ne_code", height=260)
        if c_err := validate_code(ss.ne_code):
            st.error(c_err[0])
    with right:
        st.selectbox("Category", CATEGORIES, key="ne_category")
        st.selectbox("Difficulty", DIFFICULTIES, key="ne_difficulty")
        st.text_input("Tags (comma separated)", key="ne_tags")
        st.selectbox("Status", STATUSES, key="ne_status")
    b1, b2, b3 = st.columns(3)
    b1.button("1 · Explain & Suggest", on_click=do_suggest, use_container_width=True)
    b2.button("2 · Run Tests", on_click=do_tests, use_container_width=True)
    b3.button("3 · Save entry", on_click=do_save, type="primary", use_container_width=True)
    for err in ss.ne_errors:
        st.error(err)
    if ss.ne_explanation or ss.ne_improved:
        st.subheader("AI assistant output" + (f"  ·  source: {ss.ne_source}" if ss.ne_source else ""))
        st.markdown("**Explanation**\n\n" + (ss.ne_explanation or "_none_"))
        st.text_area("Suggested improvement (editable)", key="ne_improved", height=220)
        st.markdown("**Rationale**\n\n" + (ss.ne_rationale or "_none_"))
        diff = diff_code(ss.ne_code, ss.ne_improved or ss.ne_code)
        st.markdown("**Diff** (formatting normalised, comments omitted)")
        st.code(diff or "No differences.", language="diff")
    if ss.ne_results:
        st.subheader("Test results")
        results_panel(NotebookEntry.from_dict(ss.ne_results))

# ---------------------------------------------------------------- Browse & search
elif PAGE == "Browse & Search":
    st.title("Browse & Search")
    f1, f2, f3 = st.columns([2, 2, 2])
    kw = f1.text_input("Keyword", placeholder="title, tag, code, explanation…")
    cats = f2.multiselect("Category", CATEGORIES)
    stats = f3.multiselect("Status", STATUSES)
    d_from = d_to = None
    if entries:
        dmin = min(e.created_dt.date() for e in entries)
        rng = st.date_input("Created between", value=(dmin, date.today()), min_value=dmin, max_value=date.today())
        if isinstance(rng, (tuple, list)) and len(rng) == 2:
            d_from, d_to = rng
    found = search.filter_entries(entries, kw, cats, stats, d_from, d_to)
    st.caption(f"{len(found)} of {len(entries)} entries match.")
    if found:
        size = st.selectbox("Rows per page", [10, 20, 50], index=0)
        pages = max(1, -(-len(found) // size))
        page = st.number_input("Page", 1, pages, 1)
        st.dataframe(entry_table(found[(page - 1) * size: page * size]), use_container_width=True, hide_index=True)
        st.divider()
        by_id = {e.id: e for e in found}
        sel = st.selectbox("Open entry", list(by_id), format_func=lambda i: f"{i} · {by_id[i].title}")
        e = by_id[sel]
        st.subheader(e.title)
        st.caption(f"{e.category} · {e.difficulty} · tags: {', '.join(e.tags) or '–'} · created {e.created_at} · source {e.source}")
        t1, t2, t3, t4 = st.tabs(["Original", "AI suggestion", "Diff", "Tests & metrics"])
        with t1:
            st.code(e.code, language="python")
        with t2:
            st.markdown(e.explanation or "_No explanation._")
            st.code(e.improved_code or e.code, language="python")
            st.markdown(e.rationale)
        with t3:
            st.code(diff_code(e.code, e.improved_code or e.code) or "No differences.", language="diff")
        with t4:
            results_panel(e)
        a1, a2 = st.columns(2)
        new_status = a1.selectbox("Change status", STATUSES, index=STATUSES.index(e.status) if e.status in STATUSES else 0)
        if a1.button("Update status"):
            e.status = new_status
            persist(entries)
            st.rerun()
        if a2.checkbox("Confirm delete") and a2.button("Delete entry"):
            persist([x for x in entries if x.id != e.id])
            st.rerun()

# ---------------------------------------------------------------- Dashboard
elif PAGE == "Dashboard":
    st.title("Dashboard")
    if not entries:
        st.info("No data yet. Load demo data from the Home page.")
    else:
        s = summary.compute_summary(entries)
        m = st.columns(5)
        m[0].metric("Entries", s["total"])
        m[1].metric("Avg score", s["avg_score"])
        m[2].metric("Complexity", f"{s['avg_complexity_before']} → {s['avg_complexity_after']}")
        m[3].metric("Pass rate (orig)", f"{s['pass_rate_original']}%" if s["pass_rate_original"] is not None else "–")
        m[4].metric("Pass rate (improved)", f"{s['pass_rate_improved']}%" if s["pass_rate_improved"] is not None else "–")
        show_warnings(summary.get_warnings(entries, STALE_DAYS, MAX_CX))
        st.write("**By status:** " + " · ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
        figs = charts.all_charts(entries)
        r1 = st.columns(2)
        r1[0].pyplot(figs["entries_over_time"])
        r1[1].pyplot(figs["category_distribution"])
        r2 = st.columns(2)
        r2[0].pyplot(figs["complexity_before_after"])
        r2[1].pyplot(figs["test_results"])
        st.subheader("Category breakdown")
        st.dataframe(pd.DataFrame(s["category_table"]), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Import / Export
else:
    st.title("Import / Export")
    tab_i, tab_e = st.tabs(["Bulk CSV import", "Export reports"])
    with tab_i:
        st.caption("Required columns: `title, category, code`. Optional: difficulty, status, tags, created_at, "
                   "explanation, improved_code, rationale. Every row is validated; failures are logged, not fatal.")
        try:
            sample = (storage.DATA_DIR / "sample_import_with_errors.csv").read_text(encoding="utf-8")
            st.download_button("Download sample import file (includes bad rows)", sample, "sample_import.csv", "text/csv")
        except OSError:
            pass
        up = st.file_uploader("Upload CSV", type=["csv"])
        if up is not None:
            try:
                text = up.getvalue().decode("utf-8-sig")
            except UnicodeDecodeError:
                st.error("File is not valid UTF-8 text.")
                text = None
            if text is not None:
                new, errors, dupes = importer.import_csv_text(text, entries)
                st.write(f"**{len(new)}** valid · **{len(errors)}** rejected · **{dupes}** duplicate(s) skipped")
                if errors:
                    st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)
                    st.download_button("Download error log", importer.error_log_text(errors), "import_errors.txt")
                if new and st.button(f"Import {len(new)} valid row(s)", type="primary"):
                    persist(entries + new)
                    st.success(f"Imported {len(new)} entries.")
                    st.rerun()
    with tab_e:
        if not entries:
            st.info("Nothing to export yet.")
        else:
            s = summary.compute_summary(entries)
            ws = summary.get_warnings(entries, STALE_DAYS, MAX_CX)
            stamp = datetime.now().strftime("%Y%m%d")
            x = st.columns(4)
            x[0].download_button("Markdown report", exporter.to_markdown(entries, s, ws), f"report_{stamp}.md", "text/markdown")
            x[1].download_button("Text audit log", exporter.to_text_audit(entries), f"audit_{stamp}.txt")
            x[2].download_button("CSV report", exporter.to_csv(entries), f"entries_{stamp}.csv", "text/csv")
            x[3].download_button("Chart PNGs (zip)", exporter.charts_zip(charts.all_charts(entries)),
                                 f"charts_{stamp}.zip", "application/zip")
