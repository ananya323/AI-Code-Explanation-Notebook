"""Matplotlib figures (thread-safe: Figure objects, no pyplot state)."""
from matplotlib.figure import Figure

from .summary import compute_summary

BLUE, ORANGE, GREEN, RED = "#3b6ea5", "#e08a2b", "#3f9b6b", "#c8514f"


def _empty(title):
    fig = Figure(figsize=(6, 3.6))
    ax = fig.subplots()
    ax.text(0.5, 0.5, "No data yet", ha="center", va="center")
    ax.set_title(title)
    ax.set_axis_off()
    return fig


def entries_over_time(entries):
    s = compute_summary(entries)
    if not s["weekly"]:
        return _empty("Entries per week")
    labels = [w[0][5:] for w in s["weekly"]]
    fig = Figure(figsize=(6, 3.6))
    ax = fig.subplots()
    ax.bar(labels, [w[1] for w in s["weekly"]], color=BLUE)
    ax.set_ylabel("Entries")
    ax.set_xlabel("Week starting (MM-DD)")
    ax.tick_params(axis="x", rotation=45)
    ax2 = ax.twinx()
    ax2.plot(labels, [w[2] for w in s["weekly"]], color=ORANGE, marker="o")
    ax2.set_ylabel("Avg improvement score")
    ax2.set_ylim(0, 100)
    ax.set_title("Entries per week and average score")
    fig.tight_layout()
    return fig


def category_distribution(entries):
    s = compute_summary(entries)
    if not s["total"]:
        return _empty("Category distribution")
    fig = Figure(figsize=(6, 3.6))
    ax = fig.subplots()
    cats = list(s["by_category"])
    ax.barh(cats, [s["by_category"][c] for c in cats], color=GREEN)
    ax.set_xlabel("Entries")
    ax.set_title("Entries by category")
    ax.invert_yaxis()
    fig.tight_layout()
    return fig


def complexity_before_after(entries):
    t = compute_summary(entries)["category_table"]
    if not t:
        return _empty("Complexity before vs after")
    fig = Figure(figsize=(6, 3.6))
    ax = fig.subplots()
    x = range(len(t))
    ax.bar([i - 0.2 for i in x], [r["avg_complexity_before"] for r in t], 0.4, label="Before", color=ORANGE)
    ax.bar([i + 0.2 for i in x], [r["avg_complexity_after"] for r in t], 0.4, label="After", color=BLUE)
    ax.set_xticks(list(x))
    ax.set_xticklabels([r["category"] for r in t])
    ax.set_ylabel("Avg cyclomatic-style complexity")
    ax.set_title("Complexity before vs after AI suggestion")
    ax.legend()
    fig.tight_layout()
    return fig


def test_results(entries):
    data = {}
    for which in ("original", "improved"):
        res = [e.passed(which) for e in entries if e.passed(which) is not None]
        data[which] = (sum(res), len(res) - sum(res))
    if not any(sum(v) for v in data.values()):
        return _empty("Test results")
    fig = Figure(figsize=(6, 3.6))
    ax = fig.subplots()
    names = list(data)
    ax.bar(names, [data[n][0] for n in names], color=GREEN, label="Passed")
    ax.bar(names, [data[n][1] for n in names], bottom=[data[n][0] for n in names], color=RED, label="Failed")
    ax.set_ylabel("Entries")
    ax.set_title("Sandbox test results")
    ax.legend()
    fig.tight_layout()
    return fig


def all_charts(entries) -> dict:
    return {"entries_over_time": entries_over_time(entries),
            "category_distribution": category_distribution(entries),
            "complexity_before_after": complexity_before_after(entries),
            "test_results": test_results(entries)}
