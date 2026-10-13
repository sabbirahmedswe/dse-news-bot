from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Iterable, Iterator
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup, Tag

from dse_news_bot.exceptions import ParseError
from dse_news_bot.models import MarketSnapshot, News, SharePrice

logger = logging.getLogger(__name__)

_TABLE_NEWS_CLASS = 'table-news'

_TRACKER_LABEL = 'trading code'
_TITLE_LABEL = 'news title'
_CONTENT_LABEL = 'news'
_POSTED_ON_LABEL = 'post date'

_REQUIRED_LABELS = frozenset(
    (_TRACKER_LABEL, _TITLE_LABEL, _CONTENT_LABEL, _POSTED_ON_LABEL)
)

_TABLE_PRICES_CLASS = 'shares-table'
# serial, code, ltp, high, low, closep, ycp, change, trade, value (mn), volume
_PRICE_COLUMNS = 11

# "Latest Share Price On Oct 13, 2026 at 2:40 PM"; \s+ throughout, since the
# heading may use &nbsp;
_AS_OF_PATTERN = re.compile(
    r'On\s+([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})\s+at\s+(\d{1,2}):(\d{2})\s*([AP]M)',
    re.IGNORECASE,
)
# matched by hand rather than with strptime's %b, which follows the locale
_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')

# DSE prints "--" where a price doesn't exist: the change of an untraded ticker,
# and the previous close, high or low of a new or suspended one. Counts and LTP
# always carry a number.
_NO_VALUE = '--'


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

    # titles read "EXCH: Daily Turnover";
    _, separator, remainder = fields[_TITLE_LABEL].partition(': ')
    title = remainder if separator else fields[_TITLE_LABEL]

    return News(
        tracker=fields[_TRACKER_LABEL],
        title=title,
        content=fields[_CONTENT_LABEL],
        posted_on=posted_on,
    )



def parse_price_page(html: str) -> MarketSnapshot:
    """Extract every ticker's row from the latest share price page.

    A row that doesn't have the expected shape or numbers is skipped with a
    warning, so one odd ticker doesn't cost the whole update.
    """
    soup = BeautifulSoup(html, 'html.parser')
    as_of = _parse_as_of(soup)
    price_table = soup.find('table', class_=_TABLE_PRICES_CLASS)

    if not isinstance(price_table, Tag):
        return MarketSnapshot(as_of=as_of, prices=())

    # the page closes <tbody> after every row, so rows are not all inside it
    prices = []

    for row in price_table.find_all('tr'):
        cells = [_clean_text(cell) for cell in row.find_all('td')]

        if len(cells) != _PRICE_COLUMNS:
            continue

        try:
            prices.append(_build_share_price(cells))
        except ParseError as err:
            logger.warning('Skipping price row: %s', err)

    return MarketSnapshot(as_of=as_of, prices=tuple(prices))


def _parse_as_of(soup: BeautifulSoup) -> dt.datetime | None:
    heading = soup.find(string=_AS_OF_PATTERN)
    match = _AS_OF_PATTERN.search(heading) if heading else None

    if match is None:
        return None

    month, day, year, hour, minute, meridiem = match.groups()

    try:
        hour_24 = int(hour) % 12 + (12 if meridiem.upper() == 'PM' else 0)

        return dt.datetime(
            int(year), _MONTHS.index(month.lower()) + 1, int(day), hour_24, int(minute)
        )
    except ValueError:
        return None


def _build_share_price(cells: list[str]) -> SharePrice:
    _, tracker, ltp, high, low, close, ycp, change, trade, value_mn, volume = cells

    return SharePrice(
        tracker=tracker,
        ltp=_to_decimal(ltp, tracker),
        high=_to_decimal(high, tracker, allow_missing=True),
        low=_to_decimal(low, tracker, allow_missing=True),
        close=_to_decimal(close, tracker, allow_missing=True),
        ycp=_to_decimal(ycp, tracker, allow_missing=True),
        change=_to_decimal(change, tracker, allow_missing=True),
        trade=int(_to_decimal(trade, tracker)),
        value_mn=_to_decimal(value_mn, tracker),
        volume=int(_to_decimal(volume, tracker)),
    )


def _to_decimal(value: str, tracker: str, allow_missing: bool = False) -> Decimal:
    if allow_missing and value == _NO_VALUE:
        return Decimal(0)

    # volumes carry thousands separators: "987,456"
    try:
        return Decimal(value.replace(',', ''))
    except InvalidOperation as err:
        raise ParseError(f"Unexpected number {value!r} for {tracker!r}") from err
