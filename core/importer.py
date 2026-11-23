"""Bulk CSV import with per-row validation and an error log."""
import csv
import hashlib
import io
from datetime import datetime

from .analyzer import evaluate
from .models import CATEGORIES, DIFFICULTIES, STATUSES, NotebookEntry, now_iso
from .validation import parse_tags, validate_fields

REQUIRED = ["title", "category", "code"]


def _match(value, options, default=None):
    v = (value or "").strip()
    if not v:
        return default
    return next((o for o in options if o.lower() == v.lower()), v)


def _fp(title, code):
    return hashlib.md5(f"{title.strip().lower()}|{code.strip()}".encode()).hexdigest()


def import_csv_text(text: str, existing=()):
    """Returns (new_entries, errors, duplicates). errors: [{row, title, errors}]."""
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        return [], [{"row": 1, "title": "", "errors": f"Missing required column(s): {', '.join(missing)}"}], 0
    seen = {_fp(e.title, e.code) for e in existing}
    new, errors, dupes = [], [], 0
    for n, row in enumerate(reader, start=2):
        title = (row.get("title") or "").strip()
        code = row.get("code") or ""
        category = _match(row.get("category"), CATEGORIES)
        difficulty = _match(row.get("difficulty"), DIFFICULTIES, "Easy")
        status = _match(row.get("status"), STATUSES, "Draft")
        errs = validate_fields(title, category, difficulty, status, code)
        if errs:
            errors.append({"row": n, "title": title, "errors": "; ".join(errs)})
            continue
        fp = _fp(title, code)
        if fp in seen:
            dupes += 1
            continue
        seen.add(fp)
        created = row.get("created_at") or ""
        try:
            datetime.fromisoformat(created)
        except ValueError:
            created = now_iso()
        e = NotebookEntry(title=title, category=category, code=code, difficulty=difficulty, status=status,
                          tags=parse_tags(row.get("tags")), source="import",
                          explanation=row.get("explanation") or "", improved_code=row.get("improved_code") or "",
                          rationale=row.get("rationale") or "")
        evaluate(e, run_tests=False)
        e.created_at = e.updated_at = created
        new.append(e)
    return new, errors, dupes


def error_log_text(errors) -> str:
    if not errors:
        return "No errors."
    return "\n".join(f"Row {e['row']}: {e['title'] or '(no title)'} -> {e['errors']}" for e in errors)
