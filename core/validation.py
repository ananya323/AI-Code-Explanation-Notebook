"""Centralised, defensive input validation."""
import ast
import re

from .models import CATEGORIES, DIFFICULTIES, STATUSES

MAX_CODE_CHARS = 5000
MIN_TITLE, MAX_TITLE = 3, 80
MAX_TAGS = 8


def validate_title(title) -> list:
    t = (title or "").strip()
    if len(t) < MIN_TITLE:
        return [f"Title must be at least {MIN_TITLE} characters."]
    if len(t) > MAX_TITLE:
        return [f"Title must be at most {MAX_TITLE} characters (currently {len(t)})."]
    if not re.search(r"[A-Za-z0-9]", t):
        return ["Title must contain letters or numbers."]
    return []


def validate_code(code, label="Code") -> list:
    if not code or not code.strip():
        return [f"{label} cannot be empty."]
    if len(code) > MAX_CODE_CHARS:
        return [f"{label} is too long ({len(code)} > {MAX_CODE_CHARS} characters)."]
    try:
        ast.parse(code)
    except SyntaxError as e:
        return [f"{label} has a syntax error on line {e.lineno}: {e.msg}"]
    except (ValueError, RecursionError) as e:
        return [f"{label} could not be parsed: {e}"]
    return []


def parse_tags(raw) -> list:
    """Sanitise tags from a comma/space separated string or a list."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = re.split(r"[,\s|]+", raw)
    out = []
    for t in raw:
        t = re.sub(r"[^a-z0-9_-]", "", str(t).lower())[:20]
        if t and t not in out:
            out.append(t)
    return out[:MAX_TAGS]


def validate_fields(title, category, difficulty, status, code, tags=None, improved_code="") -> list:
    errors = validate_title(title)
    if category not in CATEGORIES:
        errors.append(f"Category must be one of: {', '.join(CATEGORIES)}.")
    if difficulty not in DIFFICULTIES:
        errors.append(f"Difficulty must be one of: {', '.join(DIFFICULTIES)}.")
    if status not in STATUSES:
        errors.append(f"Status must be one of: {', '.join(STATUSES)}.")
    errors += validate_code(code)
    if improved_code and improved_code.strip():
        errors += validate_code(improved_code, "Improved code")
    return errors
