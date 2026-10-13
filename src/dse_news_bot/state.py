from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path

from dse_news_bot.models import News

_RETENTION = dt.timedelta(days=7)
_DIGEST_LEN = 12

logger = logging.getLogger(__name__)


class SentLog:
    """Which news items have already reached Telegram, kept in a JSON file.

    Maps a per-news key to the date it was sent, so entries can age out.
    """

    def __init__(self, path: Path, entries: dict[str, str]) -> None:
        self._path = path
        self._entries = entries

    @classmethod
    def load(cls, path: Path) -> SentLog:
        """Read the log, treating a missing or damaged file as an empty one.

        A broken state file should cost a duplicate message, not a failed run.
        """
        try:
            entries = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return cls(path, {})
        except (OSError, ValueError) as err:
            logger.warning(
                "State log %s unreadable (%s) - starting empty, items may be re-sent", path, err
            )
            return cls(path, {})

        if not isinstance(entries, dict):
            logger.warning(
                "State log %s is not a JSON object - starting empty, items may be re-sent", path
            )
            return cls(path, {})

        return cls(path, {str(key): str(value) for key, value in entries.items()})

    def has(self, news: News) -> bool:
        return _key(news) in self._entries

    def mark(self, news: News) -> None:
        self._entries[_key(news)] = dt.date.today().isoformat()

    def has_market_update(self, day: dt.date) -> bool:
        return _market_key(day) in self._entries

    def mark_market_update(self, day: dt.date) -> None:
        self._entries[_market_key(day)] = dt.date.today().isoformat()

    def save(self) -> None:
        """Write the pruned log atomically, so an interrupted run leaves valid JSON."""
        self._prune()
        self._path.parent.mkdir(parents=True, exist_ok=True)

        tmp = self._path.with_suffix(f"{self._path.suffix}.tmp")
        tmp.write_text(json.dumps(self._entries, indent=2, sort_keys=True), encoding='utf-8')
        os.replace(tmp, self._path)

    def _prune(self) -> None:
        cutoff = dt.date.today() - _RETENTION

        self._entries = {
            key: sent_on
            for key, sent_on in self._entries.items()
            if _as_date(sent_on) >= cutoff
        }


def _key(news: News) -> str:
    """Identify a news item by ticker, date and a digest of its text.

    Hashing the body means a revised notice for the same ticker and day is
    treated as new and sent again.
    """
    digest = hashlib.sha1(f"{news.title}{news.content}".encode('utf-8')).hexdigest()

    return f"{news.tracker}|{news.posted_on.isoformat()}|{digest[:_DIGEST_LEN]}"


def _market_key(day: dt.date) -> str:
    """One key per trading day: the market update goes out at most once a day."""
    return f"market|{day.isoformat()}"


def _as_date(value: str) -> dt.date:
    """Parse a stored date, keeping unreadable entries until the next run."""
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return dt.date.today()
