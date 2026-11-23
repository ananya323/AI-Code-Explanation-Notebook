"""Generate 40 realistic demo entries (normal, boundary and edge cases) + sample files."""
import csv
import json
import random
import shutil
from datetime import datetime, timedelta

from core import storage
from core.ai_assistant import suggest
from core.analyzer import evaluate
from core.models import DIFFICULTIES, NotebookEntry

SNIPPETS = [
    ("Filter even numbers", "Performance", ["loops", "lists"],
     "def evens(nums):\n    result = []\n    for n in nums:\n        if n % 2 == 0:\n            result.append(n)\n    return result\n\nprint(evens(range(10)))\n"),
    ("Greeting with None check", "Style", ["none", "pep8"],
     "def greet(name):\n    if name == None:\n        return 'Hello, stranger'\n    return 'Hello, ' + name\n\nprint(greet(None))\nprint(greet('Ada'))\n"),
    ("Adult age check", "Readability", ["booleans"],
     "def is_adult(age):\n    if age >= 18:\n        return True\n    else:\n        return False\n\nprint(is_adult(20), is_adult(12))\n"),
    ("Squares list", "Performance", ["loops", "comprehension"],
     "def squares(n):\n    out = []\n    for i in range(n):\n        out.append(i * i)\n    return out\n\nprint(squares(6))\n"),
    ("Safe division", "Safety", ["errors"],
     "def safe_div(a, b):\n    try:\n        return a / b\n    except:\n        return None\n\nprint(safe_div(4, 2), safe_div(1, 0))\n"),
    ("Recursive Fibonacci", "Performance", ["recursion"],
     "def fib(n):\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)\n\nprint([fib(i) for i in range(12)])\n"),
    ("Word frequency counter", "Readability", ["dicts", "text"],
     "def count_words(text):\n    counts = {}\n    for w in text.split():\n        if w in counts:\n            counts[w] = counts[w] + 1\n        else:\n            counts[w] = 1\n    return counts\n\nprint(count_words('a b a c b a'))\n"),
    ("Average of empty list", "Bug Fix", ["edge-case", "zerodivision"],
     "def average(nums):\n    return sum(nums) / len(nums)\n\nprint(average([1, 2, 3]))\nprint(average([]))\n"),
    ("Pair sum finder", "Performance", ["nested-loops"],
     "def find_pairs(nums, target):\n    pairs = []\n    for i in range(len(nums)):\n        for j in range(i + 1, len(nums)):\n            if nums[i] + nums[j] == target:\n                pairs.append((nums[i], nums[j]))\n    return pairs\n\nprint(find_pairs([1, 2, 3, 4, 5], 6))\n"),
    ("Hello script", "Style", ["script"], "print('hello world')\n"),
]
ROUNDS = ["", " v2", " v3", " v4"]


def build(n: int = 40, seed: int = 42) -> list:
    rnd = random.Random(seed)
    now = datetime.now().replace(microsecond=0)
    entries = []
    for i in range(n):
        title, cat, tags, code = SNIPPETS[i % len(SNIPPETS)]
        title = title + ROUNDS[(i // len(SNIPPETS)) % len(ROUNDS)]
        if i == 10:
            title = "Abc"                      # boundary: minimum title length
        if i == 20:
            title = "Boundary: " + "x" * 70    # boundary: maximum title length (80)
        res = suggest(code, cat)
        e = NotebookEntry(title=title, category=cat, code=code, difficulty=rnd.choice(DIFFICULTIES),
                          explanation=res["explanation"], improved_code=res["improved_code"],
                          rationale=res["rationale"], tags=tags, source="seed")
        evaluate(e, run_tests=True)
        if e.passed("improved") is False:
            e.status = rnd.choice(["Draft", "Rejected"])
        elif e.score < 45:
            e.status = "Rejected"
        else:
            e.status = rnd.choices(["Draft", "Tested", "Documented"], [2, 4, 4])[0]
        created = now - timedelta(days=rnd.randint(0, 55), hours=rnd.randint(0, 23), minutes=rnd.randint(0, 59))
        e.created_at = e.updated_at = created.isoformat()
        entries.append(e)
    return sorted(entries, key=lambda e: e.created_at)


def write_samples(entries) -> None:
    d = storage.DATA_DIR
    d.mkdir(exist_ok=True)
    (d / "sample_entries.json").write_text(
        json.dumps({"schema_version": 1, "entries": [e.to_dict() for e in entries]}, indent=2), encoding="utf-8")
    (d / "sample_entries.csv").write_text(storage.entries_to_csv_text(entries), encoding="utf-8", newline="")
    rows = [
        ["title", "category", "difficulty", "status", "tags", "code"],
        ["Valid import row", "Style", "Easy", "Draft", "demo", "def f(x):\n    return x == None\n"],
        ["Another valid row", "performance", "Medium", "Tested", "demo,loops", "print(sum(range(10)))\n"],
        ["Bad category", "Magic", "Easy", "Draft", "", "print(1)\n"],
        ["Empty code", "Style", "Easy", "Draft", "", ""],
        ["Syntax problem", "Bug Fix", "Easy", "Draft", "", "def broken(:\n    pass\n"],
        ["ab", "Style", "Easy", "Draft", "", "print(2)\n"],
        ["Bad status", "Safety", "Easy", "Finished", "", "print(3)\n"],
    ]
    with open(d / "sample_import_with_errors.csv", "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


def seed(n: int = 40, path=None) -> list:
    entries = build(n)
    storage.save_entries(entries, path or storage.JSON_PATH)
    write_samples(entries)
    return entries


if __name__ == "__main__":
    es = seed()
    print(f"Seeded {len(es)} entries into {storage.JSON_PATH}")
