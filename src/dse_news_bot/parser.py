from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Iterator

from bs4 import BeautifulSoup, Tag

from dse_news_bot.exceptions import ParseError
from dse_news_bot.models import News

_TABLE_NEWS_CLASS = 'table-news'

_TRACKER_LABEL = 'trading code'
_TITLE_LABEL = 'news title'
_CONTENT_LABEL = 'news'
_POSTED_ON_LABEL = 'post date'

_REQUIRED_LABELS = frozenset(
    (_TRACKER_LABEL, _TITLE_LABEL, _CONTENT_LABEL, _POSTED_ON_LABEL)
)


def parse_news_page(html: str) -> list[News]:
    """Extract every complete news item from an archive page.

    Incomplete blocks (a truncated page, an unexpected layout) are skipped;
    a malformed post date raises :class:`ParseError`.
    """
    soup = BeautifulSoup(html, 'html.parser')
    news_table = soup.find('table', class_=_TABLE_NEWS_CLASS)

    if not isinstance(news_table, Tag):
        return []

    return [_build_news(fields) for fields in _iter_news_fields(news_table.find_all('tr'))]


def _iter_news_fields(rows: Iterable[Tag]) -> Iterator[dict[str, str]]:
    """Yield one label -> value mapping per complete news block."""
    fields: dict[str, str] = {}

    for row in rows:
        label, value = _read_row(row)

        # separators and spacers carry a <th> only
        if value is None:
            continue

        # the trading code opens a block, so anything half-collected is stale
        if label == _TRACKER_LABEL:
            fields = {}

        fields[label] = value

        if _REQUIRED_LABELS.issubset(fields):
            yield fields
            fields = {}


def _read_row(row: Tag) -> tuple[str, str | None]:
    """Return the row's normalized label and value, or ``None`` when it has no value cell."""
    value_cell = row.find('td')

    if not isinstance(value_cell, Tag):
        return '', None

    return _normalize_label(row.find('th')), _clean_text(value_cell)


def _normalize_label(tag: Tag | None) -> str:
    if not isinstance(tag, Tag):
        return ''

    return tag.get_text(strip=True).rstrip(':').lower()


def _clean_text(tag: Tag) -> str:
    """Collapse the source's line wrapping and indentation into single-spaced text."""
    return ' '.join(tag.get_text(strip=True).split())


def _build_news(fields: dict[str, str]) -> News:
    posted_on = fields[_POSTED_ON_LABEL]

    try:
        posted_on = dt.date.fromisoformat(posted_on)
    except ValueError as err:
        tracker = fields[_TRACKER_LABEL]
        raise ParseError(f"Unexpected post date {posted_on!r} for {tracker!r}") from err

    title = fields.get(_TITLE_LABEL, '').split(': ')[1]

    return News(
        tracker=fields[_TRACKER_LABEL],
        title=fields[_TITLE_LABEL],
        content=fields[_CONTENT_LABEL],
        posted_on=posted_on,

    )
