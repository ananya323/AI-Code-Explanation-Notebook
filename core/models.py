"""Data model for notebook entries."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime

CATEGORIES = ["Performance", "Readability", "Bug Fix", "Style", "Safety"]
STATUSES = ["Draft", "Tested", "Documented", "Rejected"]
DIFFICULTIES = ["Easy", "Medium", "Hard"]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class NotebookEntry:
    title: str
    category: str
    code: str
    difficulty: str = "Easy"
    explanation: str = ""
    improved_code: str = ""
    rationale: str = ""
    status: str = "Draft"
    tags: list = field(default_factory=list)
    metrics_before: dict = field(default_factory=dict)
    metrics_after: dict = field(default_factory=dict)
    test_original: dict = field(default_factory=dict)
    test_improved: dict = field(default_factory=dict)
    score: float = 0.0
    source: str = "mock"
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "NotebookEntry":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    def passed(self, which: str):
        """True/False if tests were run for 'original' or 'improved', else None."""
        res = getattr(self, f"test_{which}")
        return None if not res else res.get("status") == "passed"

    @property
    def created_dt(self) -> datetime:
        try:
            return datetime.fromisoformat(self.created_at)
        except ValueError:
            return datetime.now()
