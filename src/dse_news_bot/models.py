from __future__ import annotations

from dataclasses import dataclass
import datetime as dt

@dataclass(frozen=True)
class News:
    tracker: str
    title: str
    content: str
    published_on: dt.date

    def __repr__(self):
        return f"[{self.published_on.isoformat()}] {self.tracker}\n\n{self.content}\n"
    