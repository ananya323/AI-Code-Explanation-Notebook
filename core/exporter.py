"""Markdown, plain-text audit log, CSV and chart exports."""
import io
import zipfile
from datetime import datetime

from .storage import entries_to_csv_text


def to_markdown(entries, summary, warnings) -> str:
    L = ["# AI Code Explanation Notebook — Report", f"_Generated {datetime.now():%Y-%m-%d %H:%M}_", "",
         "## Executive summary", "",
         f"- **Total entries:** {summary['total']}",
         f"- **Average improvement score:** {summary['avg_score']}",
         f"- **Avg complexity:** {summary['avg_complexity_before']} → {summary['avg_complexity_after']}",
         f"- **Test pass rate (original / improved):** {summary['pass_rate_original']}% / {summary['pass_rate_improved']}%",
         "- **By status:** " + ", ".join(f"{k}: {v}" for k, v in summary["by_status"].items()),
         "- **By category:** " + ", ".join(f"{k}: {v}" for k, v in summary["by_category"].items()), ""]
    if warnings:
        L += ["## Warnings", ""] + [f"- ({w['level']}) {w['message']}" for w in warnings] + [""]
    L += ["## Entries", ""]
    for e in sorted(entries, key=lambda e: e.created_at, reverse=True):
        L += [f"### {e.title}", f"`{e.id}` · {e.category} · {e.difficulty} · **{e.status}** · score {e.score} · {e.created_at}",
              "", "**Explanation:** " + (e.explanation or "_none_"), "", "**Original**", "```python", e.code, "```"]
        if e.improved_code:
            L += ["**Improved**", "```python", e.improved_code, "```"]
        if e.rationale:
            L += ["**Rationale**", e.rationale]
        L.append("")
    return "\n".join(L)


def to_text_audit(entries) -> str:
    L = [f"AUDIT LOG generated {datetime.now():%Y-%m-%d %H:%M:%S}", "=" * 78]
    for e in sorted(entries, key=lambda e: e.created_at):
        L.append(f"{e.created_at} | {e.id} | {e.status:<10} | {e.category:<11} | score {e.score:>5} | "
                 f"orig={e.test_original.get('status', '-')} impr={e.test_improved.get('status', '-')} | {e.title}")
    return "\n".join(L)


def to_csv(entries) -> str:
    return entries_to_csv_text(entries)


def charts_zip(figures: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, fig in figures.items():
            png = io.BytesIO()
            fig.savefig(png, format="png", dpi=150)
            z.writestr(f"{name}.png", png.getvalue())
    return buf.getvalue()
