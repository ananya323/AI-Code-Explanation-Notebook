"""Aggregate metrics, trends and threshold warnings."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from .models import CATEGORIES, STATUSES


def _avg(xs):
    xs = list(xs)
    return round(sum(xs) / len(xs), 2) if xs else 0.0


def _rate(entries, which):
    tested = [e for e in entries if e.passed(which) is not None]
    return round(100 * sum(bool(e.passed(which)) for e in tested) / len(tested), 1) if tested else None


def compute_summary(entries) -> dict:
    by_status = {s: 0 for s in STATUSES}
    by_status.update(Counter(e.status for e in entries))
    by_cat = {c: 0 for c in CATEGORIES}
    by_cat.update(Counter(e.category for e in entries))
    weeks = defaultdict(list)
    for e in entries:
        d = e.created_dt.date()
        weeks[d - timedelta(days=d.weekday())].append(e.score)
    weekly = [(w.isoformat(), len(v), _avg(v)) for w, v in sorted(weeks.items())]
    table = []
    for c in CATEGORIES:
        es = [e for e in entries if e.category == c]
        if es:
            table.append({"category": c, "entries": len(es), "avg_score": _avg(e.score for e in es),
                          "avg_complexity_before": _avg(e.metrics_before.get("complexity", 0) for e in es),
                          "avg_complexity_after": _avg(e.metrics_after.get("complexity", 0) for e in es)})
    return {
        "total": len(entries), "by_status": by_status, "by_category": by_cat,
        "avg_score": _avg(e.score for e in entries),
        "avg_complexity_before": _avg(e.metrics_before.get("complexity", 0) for e in entries),
        "avg_complexity_after": _avg(e.metrics_after.get("complexity", 0) for e in entries),
        "pass_rate_original": _rate(entries, "original"), "pass_rate_improved": _rate(entries, "improved"),
        "tested_count": sum(e.passed("improved") is not None for e in entries),
        "improved_count": sum(e.score > 50 for e in entries),
        "weekly": weekly, "category_table": table,
    }


def get_warnings(entries, stale_days: int = 7, max_complexity: int = 8) -> list:
    """Threshold indicators: stale drafts, failing tests, high complexity, regressions."""
    now, out = datetime.now(), []
    for e in entries:
        age = (now - e.created_dt).days
        if e.status == "Draft" and age > stale_days:
            out.append({"level": "warning", "id": e.id, "message": f"'{e.title}' has been a Draft for {age} days."})
        if e.passed("improved") is False:
            out.append({"level": "error", "id": e.id,
                        "message": f"'{e.title}': improved code {e.test_improved.get('status')} its test run."})
        if e.metrics_after.get("complexity", 0) > max_complexity:
            out.append({"level": "warning", "id": e.id,
                        "message": f"'{e.title}': complexity {e.metrics_after['complexity']} exceeds limit {max_complexity}."})
        worse = e.metrics_after.get("complexity", 0) > e.metrics_before.get("complexity", 0)
        if worse or (e.passed("original") and e.passed("improved") is False):
            out.append({"level": "error", "id": e.id, "message": f"'{e.title}': AI suggestion made the code worse."})
    return out
