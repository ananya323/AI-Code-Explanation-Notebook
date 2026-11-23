"""Static metrics, diffing, improvement score and entry evaluation."""
import ast
import difflib

from .models import now_iso
from .sandbox import run_code


def code_metrics(code: str) -> dict:
    lines = sum(1 for l in code.splitlines() if l.strip() and not l.strip().startswith("#"))
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return {"lines": lines, "functions": 0, "complexity": 0, "docstring_coverage": 0.0, "valid": False}
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    cx = 1
    for n in ast.walk(tree):
        if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.IfExp, ast.comprehension)):
            cx += 1
        elif isinstance(n, ast.BoolOp):
            cx += len(n.values) - 1
    doc = 100.0 if not funcs else round(100 * sum(1 for f in funcs if ast.get_docstring(f)) / len(funcs), 1)
    return {"lines": lines, "functions": len(funcs), "complexity": cx, "docstring_coverage": doc, "valid": True}


def _normalize(code: str) -> str:
    try:
        return ast.unparse(ast.parse(code))
    except (SyntaxError, ValueError):
        return code


def diff_code(a: str, b: str) -> str:
    """Unified diff of normalised sources (formatting noise removed, comments dropped)."""
    return "\n".join(difflib.unified_diff(_normalize(a).splitlines(), _normalize(b).splitlines(),
                                          "original", "improved", lineterm=""))


def improvement_score(before: dict, after: dict, passed_before=None, passed_after=None) -> float:
    s = 50.0
    s += max(-20, min(20, (before.get("complexity", 0) - after.get("complexity", 0)) * 5))
    s += max(-10, min(10, (before.get("lines", 0) - after.get("lines", 0)) * 1.5))
    s += (after.get("docstring_coverage", 0) - before.get("docstring_coverage", 0)) * 0.2
    if passed_after is not None and passed_before is not None:
        if passed_after and not passed_before:
            s += 20
        elif passed_after and passed_before:
            s += 10
        elif passed_before and not passed_after:
            s -= 40
        else:
            s -= 10
    return round(max(0.0, min(100.0, s)), 1)


def evaluate(entry, run_tests: bool = True):
    """Fill metrics, (optionally) run both versions in the sandbox, compute score."""
    improved = entry.improved_code if entry.improved_code.strip() else entry.code
    entry.metrics_before = code_metrics(entry.code)
    entry.metrics_after = code_metrics(improved)
    if run_tests:
        entry.test_original = run_code(entry.code)
        entry.test_improved = run_code(improved)
    entry.score = improvement_score(entry.metrics_before, entry.metrics_after,
                                    entry.passed("original"), entry.passed("improved"))
    entry.updated_at = now_iso()
    return entry
