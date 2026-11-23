"""Keyword / category / status / date filtering."""


def filter_entries(entries, keyword="", categories=None, statuses=None, date_from=None, date_to=None):
    kw = (keyword or "").strip().lower()
    out = []
    for e in entries:
        if categories and e.category not in categories:
            continue
        if statuses and e.status not in statuses:
            continue
        d = e.created_dt.date()
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        if kw:
            hay = " ".join([e.title, e.category, " ".join(e.tags), e.explanation, e.code, e.id]).lower()
            if not all(word in hay for word in kw.split()):
                continue
        out.append(e)
    return sorted(out, key=lambda e: e.created_at, reverse=True)
