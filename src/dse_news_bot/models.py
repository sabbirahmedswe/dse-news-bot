from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import datetime as dt

@dataclass(frozen=True)
class News:
    tracker: str
    title: str
    content: str
    posted_on: dt.date

    def __repr__(self):
        return f"[{self.posted_on.isoformat()}] {self.tracker}\n\n{self.content}\n"
    

@dataclass(frozen=True)
class SharePrice:
    tracker: str
    ltp: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    ycp: Decimal
    change: Decimal
    trade: int
    value_mn: Decimal
    volume: int


@dataclass(frozen=True)
class MarketSnapshot:
    # None when the page heading is missing or reworded
    as_of: dt.datetime | None
    prices: tuple[SharePrice, ...]
