"""JSON persistence (with CSV mirror), atomic writes and corruption recovery."""
import csv
import io
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from .models import NotebookEntry

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
JSON_PATH = DATA_DIR / "entries.json"
SCHEMA_VERSION = 1

CSV_FIELDS = ["id", "title", "category", "difficulty", "status", "tags", "created_at",
              "updated_at", "score", "complexity_before", "complexity_after",
              "test_original", "test_improved", "code", "improved_code",
              "explanation", "rationale"]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def entries_to_csv_text(entries) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    w.writeheader()
    for e in entries:
        w.writerow({
            "id": e.id, "title": e.title, "category": e.category,
            "difficulty": e.difficulty, "status": e.status, "tags": "|".join(e.tags),
            "created_at": e.created_at, "updated_at": e.updated_at, "score": e.score,
            "complexity_before": e.metrics_before.get("complexity", ""),
            "complexity_after": e.metrics_after.get("complexity", ""),
            "test_original": e.test_original.get("status", ""),
            "test_improved": e.test_improved.get("status", ""),
            "code": e.code, "improved_code": e.improved_code,
            "explanation": e.explanation, "rationale": e.rationale,
        })
    return buf.getvalue()


def save_entries(entries, path: Path = JSON_PATH, mirror_csv: bool = True) -> None:
    path = Path(path)
    payload = {"schema_version": SCHEMA_VERSION, "entries": [e.to_dict() for e in entries]}
    _atomic_write(path, json.dumps(payload, indent=2))
    if mirror_csv:
        _atomic_write(path.with_suffix(".csv"), entries_to_csv_text(entries))


def load_entries(path: Path = JSON_PATH):
    """Return (entries, notice). Never raises on missing/corrupt files."""
    path = Path(path)
    if not path.exists():
        save_entries([], path)
        return [], None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list):
            raise ValueError("unexpected schema")
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError, OSError) as exc:
        backup = path.with_name(f"{path.name}.corrupt-{datetime.now():%Y%m%d%H%M%S}")
        try:
            path.replace(backup)
        except OSError:
            pass
        save_entries([], path)
        return [], f"Data file was unreadable ({exc}). Backed up to {backup.name} and started fresh."
    entries, skipped = [], 0
    for row in raw["entries"]:
        try:
            entries.append(NotebookEntry.from_dict(row))
        except (TypeError, AttributeError):
            skipped += 1
    return entries, (f"Skipped {skipped} malformed record(s) while loading." if skipped else None)
