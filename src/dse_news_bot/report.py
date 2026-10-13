from __future__ import annotations

import html as html_lib
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from dse_news_bot.models import MarketSnapshot, SharePrice

_TITLE = "Today's Update"

_UP = '▲'
_DOWN = '▼'

_CENT = Decimal('0.01')


def format_market_update(snapshot: MarketSnapshot, portfolio: Iterable[str]) -> str:
    """Render the portfolio's prices as plain text: a title over a fixed-width table."""
    lines, note = _layout(snapshot, portfolio)
    sections = [_TITLE, '\n'.join(lines), note]

    return '\n\n'.join(section for section in sections if section)


def format_market_messages(
    snapshot: MarketSnapshot, portfolio: Iterable[str], max_len: int
) -> list[str]:
    """Render the update as Telegram HTML, split into messages of at most ``max_len``.

    A bold title, then the table in ``<pre>`` blocks so its columns stay aligned.
    Splits fall between rows, each part a complete ``<pre>`` block, since a cut
    through a tag leaves HTML that Telegram rejects. ``max_len`` is checked
    against the HTML source, which is never shorter than the text Telegram counts.
    """
    lines, note = _layout(snapshot, portfolio)

    messages: list[str] = []
    current = f"<b>{_TITLE}</b>"
    block: list[str] = []

    for line in (html_lib.escape(line, quote=False) for line in lines):
        if block and len(_with_block(current, block + [line])) > max_len:
            messages.append(_with_block(current, block))
            current, block = '', []

        block.append(line)

    current = _with_block(current, block) if block else current
    note = html_lib.escape(note, quote=False)

    if note and len(f"{current}\n\n{note}") > max_len:
        messages.append(current)
        current = note
    elif note:
        current = f"{current}\n\n{note}"

    messages.append(current)

    return messages


def _with_block(head: str, block: list[str]) -> str:
    pre = '<pre>' + '\n'.join(block) + '</pre>'

    return f"{head}\n\n{pre}" if head else pre


def _layout(snapshot: MarketSnapshot, portfolio: Iterable[str]) -> tuple[list[str], str]:
    """Return the aligned table lines and the note on tickers missing from the page."""
    by_tracker = {price.tracker.upper(): price for price in snapshot.prices}
    watched = sorted({code.strip().upper() for code in portfolio})

    rows = [_row(by_tracker[code]) for code in watched if code in by_tracker]
    # zip(*rows) yields nothing when no ticker matched
    widths = [max(len(cell) for cell in column) for column in zip(*rows)]

    missing = [code for code in watched if code not in by_tracker]
    note = f"Not on the price page: {', '.join(missing)}" if missing else ''

    return [_align(row, widths) for row in rows], note


def _row(price: SharePrice) -> tuple[str, ...]:
    # an untraded ticker has LTP 0; its last price is yesterday's close
    if not price.trade:
        return (price.tracker, _money(price.ycp), 'no trades')

    return (price.tracker, _money(price.ltp), _change_pct(price))


def _align(row: tuple[str, ...], widths: list[int]) -> str:
    # code left-aligned, numbers right-aligned
    cells = [row[0].ljust(widths[0])] + [cell.rjust(width) for cell, width in zip(row[1:], widths[1:])]

    return '  '.join(cells).rstrip()


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _change_pct(price: SharePrice) -> str:
    # a fresh listing has no previous close to compare against
    if not price.ycp:
        return ''

    # rounded first, so the arrow agrees with the digits: +0.004% is 0.00%
    pct = ((price.ltp - price.ycp) * 100 / price.ycp).quantize(_CENT, ROUND_HALF_UP)

    if pct > 0:
        return f"{_UP} {pct:+.2f}%"

    if pct < 0:
        return f"{_DOWN} {pct:+.2f}%"

    return f"{abs(pct):.2f}%"
