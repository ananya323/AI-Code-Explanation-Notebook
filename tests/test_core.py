import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import importer, search, storage, summary
from core.ai_assistant import mock_suggest, suggest
from core.analyzer import code_metrics, evaluate, improvement_score
from core.models import NotebookEntry
from core.sandbox import run_code
from core.validation import parse_tags, validate_code, validate_fields, validate_title


def test_validation():
    assert validate_title("ab") and not validate_title("abc")
    assert validate_title("x" * 81) and not validate_title("x" * 80)
    assert validate_code("") and validate_code("   ")
    assert "syntax error" in validate_code("def f(:")[0]
    assert validate_code("x" * 6000)
    assert not validate_code("print(1)")
    assert parse_tags("Foo, bar!! foo  BAZ") == ["foo", "bar", "baz"]
    assert validate_fields("Good title", "Nope", "Easy", "Draft", "print(1)")


def test_storage_roundtrip_and_recovery(tmp_path):
    p = tmp_path / "entries.json"
    es, note = storage.load_entries(p)          # missing -> template
    assert es == [] and p.exists()
    e = evaluate(NotebookEntry(title="T1x", category="Style", code="print(1)"), run_tests=False)
    storage.save_entries([e], p)
    assert (tmp_path / "entries.csv").exists()
    assert storage.load_entries(p)[0][0].id == e.id
    p.write_text("{not json")                   # corrupted
    es, note = storage.load_entries(p)
    assert es == [] and "unreadable" in note
    assert list(tmp_path.glob("entries.json.corrupt-*"))
    p.write_text(json.dumps({"entries": [{"bad": 1}]}))
    es, note = storage.load_entries(p)
    assert es == [] and "malformed" in note


def test_mock_improvements_preserve_behaviour():
    code = "def f(n):\n    out = []\n    for i in range(n):\n        if i % 2 == 0:\n            out.append(i)\n    return out\nprint(f(6))\n"
    res = mock_suggest(code, "Performance")
    assert "[i for i in range(n) if i % 2 == 0]" in res["improved_code"]
    assert run_code(code)["stdout"] == run_code(res["improved_code"])["stdout"]
    r2 = mock_suggest("def g(x):\n    if x == None:\n        return True\n    return False\n", "Style")
    assert "x is None" in r2["improved_code"]
    assert suggest("print(1)", "Style", use_api=True, api_key="")["source"].startswith("mock")


def test_sandbox():
    assert run_code("print('hi')")["status"] == "passed"
    assert run_code("1/0")["status"] == "failed"
    assert run_code("import os")["status"] == "blocked"
    assert run_code("eval('1')")["status"] == "blocked"
    assert run_code("while True: pass", timeout=1)["status"] == "timeout"


def test_metrics_and_score():
    m = code_metrics("def f(x):\n    if x and x > 1:\n        return 1\n    return 0\n")
    assert m["functions"] == 1 and m["complexity"] == 3 and m["docstring_coverage"] == 0.0
    assert improvement_score({"complexity": 5}, {"complexity": 3}, True, True) > 50
    assert improvement_score({"complexity": 3}, {"complexity": 3}, True, False) < 20


def test_search_summary_warnings():
    import seed_data
    es = seed_data.build(40)
    assert len(es) == 40
    assert search.filter_entries(es, "fibonacci")
    assert all(e.category == "Safety" for e in search.filter_entries(es, categories=["Safety"]))
    s = summary.compute_summary(es)
    assert s["total"] == 40 and sum(s["by_status"].values()) == 40
    assert summary.get_warnings(es)


def test_importer():
    csv_text = ("title,category,code\nGood one,Style,print(1)\nBad,Magic,print(2)\nNoCode,Style,\n"
                "Broken,Style,\"def f(:\n\"\nab,Style,print(3)\n")
    new, errors, dupes = importer.import_csv_text(csv_text)
    assert len(new) == 1 and len(errors) == 4
    new2, _, d2 = importer.import_csv_text(csv_text, existing=new)
    assert not new2 and d2 == 1
    assert importer.import_csv_text("a,b\n1,2")[1][0]["row"] == 1
