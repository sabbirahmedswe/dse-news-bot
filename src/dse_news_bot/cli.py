from __future__ import annotations

import datetime as dt
import io
import logging
import sys
from collections.abc import Callable

from dse_news_bot.config import Config
from dse_news_bot.exceptions import ConfigError, FetchError, NotifyError, ParseError
from dse_news_bot.client import DseNewsClient
from dse_news_bot.logs import setup_logging
from dse_news_bot.notifier import TelegramNotifier
from dse_news_bot.parser import parse_news_page, parse_price_page
from dse_news_bot.report import format_market_update
from dse_news_bot.models import MarketSnapshot
from dse_news_bot.state import SentLog

_CHAT_ID_FLAG = '--chat-id'
_MARKET_FLAG = '--market'
_DRY_RUN_FLAG = '--dry-run'

_FLAG_SETS = (
    frozenset(),
    frozenset({_CHAT_ID_FLAG}),
    frozenset({_MARKET_FLAG}),
    frozenset({_MARKET_FLAG, _DRY_RUN_FLAG}),
)
_USAGE = 'usage: dse-news-bot [--chat-id | --market [--dry-run]]'

# DSE's clock, whatever the machine's says; Bangladesh has no daylight saving
_DHAKA = dt.timezone(dt.timedelta(hours=6), 'BST')

# DSE closes at 14:30; prices stamped earlier are a mid-session snapshot
_MARKET_CLOSE = dt.time(14, 30)
# by now a stamp from earlier today means the page stopped at the bell, not
# that the close is still to come
_CLOSE_STAMP_DEADLINE = dt.time(15, 30)

logger = logging.getLogger(__package__)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    _use_utf8_streams()

    setup_logging()

    if frozenset(argv) not in _FLAG_SETS:
        logger.error('%s', _USAGE)
        return 2

    if _CHAT_ID_FLAG in argv:
        steps = [_print_chat_ids]
    elif _MARKET_FLAG in argv and _DRY_RUN_FLAG in argv:
        steps = [_print_market_update]
    elif _MARKET_FLAG in argv:
        steps = [_send_market_update]
    else:
        # one scheduled task covers both: news all day, the market update once
        # after the close
        steps = [_send_todays_news, _send_market_update]

    # every step runs, so a news failure doesn't cost the market update
    results = [_run(step) for step in steps]

    return 0 if all(results) else 1


def _run(step: Callable[[], None]) -> bool:
    try:
        step()
    except (ConfigError, FetchError, ParseError, NotifyError) as err:
        logger.error('%s', err)
        return False
    except Exception:
        logger.exception('Unexpected failure')
        return False

    return True


def _use_utf8_streams() -> None:
    """Make stdout and stderr UTF-8 for every mode.

    Redirected output (a pipe, the scheduler) falls back to cp1252 on Windows,
    which can't encode the market update's arrows - nor Bengali text in a news
    item that ends up in a log line. Logs go to stderr, so both streams need it.
    """
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding='utf-8', errors='replace')


def _send_todays_news() -> None:
    config = Config.load()

    with DseNewsClient() as client:
        html = client.fetch()

    sent = SentLog.load(config.state_path)
    news_items = parse_news_page(html)
    pending = [
        news for news in news_items
        if news.tracker.upper() in config.portfolio and not sent.has(news)
    ]

    logger.info('Parsed %d news items, %d pending for your portfolio', len(news_items), len(pending))

    if not pending:
        return

    try:
        with TelegramNotifier(config.bot_token) as bot:
            for news in pending:
                bot.send_news(config.chat_id, news)
                # only after the send, so a failure is retried next run
                sent.mark(news)
                logger.info("Sent %s: %s", news.tracker, news.title)
    finally:
        sent.save()


def _send_market_update() -> None:
    """Send the closing prices to Telegram, at most once per trading day.

    Runs every 5 minutes with the news, so the cheap checks come first and the
    price page is fetched only once the market has closed and today's update is
    still owed.
    """
    config = Config.load()
    # naive, to compare with the page's own (Dhaka) timestamp
    now = dt.datetime.now(_DHAKA).replace(tzinfo=None)
    today = now.date()
    sent = SentLog.load(config.state_path)

    if sent.has_market_update(today):
        logger.debug('Market update already done for today')
        return

    if now.time() < _MARKET_CLOSE:
        logger.debug('Market still open - the update waits for %s', _MARKET_CLOSE.strftime('%H:%M'))
        return

    snapshot = _fetch_snapshot()

    if snapshot.as_of is None:
        logger.warning('Price page has no readable timestamp - market update not sent')
        return

    # the page shows today's prices from the open, so after the close an older
    # stamp means no trading today; recorded, so the page isn't fetched all
    # afternoon
    if snapshot.as_of.date() < today:
        logger.info('Prices are from %s - no trading today, no market update', snapshot.as_of.date())
        sent.mark_market_update(today)
        sent.save()
        return

    if not _is_close(snapshot.as_of, now):
        logger.info("Prices as of %s are not the close yet - market update not sent", snapshot.as_of)
        return

    with TelegramNotifier(config.bot_token) as bot:
        bot.send_market_update(config.chat_id, snapshot, config.portfolio)

    sent.mark_market_update(today)
    sent.save()

    logger.info('Sent market update, prices as of %s', snapshot.as_of)


def _print_market_update() -> None:
    """Preview the update on the console: no Telegram, no time or dedup checks."""
    config = Config.load(require_chat_id=False, require_bot_token=False)
    snapshot = _fetch_snapshot()

    print(format_market_update(snapshot, config.portfolio))


def _fetch_snapshot() -> MarketSnapshot:
    with DseNewsClient() as client:
        html = client.fetch_prices()

    snapshot = parse_price_page(html)

    # a renamed table or a cut-off page parses to nothing; an update of only
    # "not on the price page" must not go out and count as done
    if not snapshot.prices:
        raise ParseError('No share prices on the price page - has its layout changed?')

    logger.info('Parsed %d share prices, as of %s', len(snapshot.prices), snapshot.as_of or 'unknown')

    return snapshot


def _is_close(as_of: dt.datetime, now: dt.datetime) -> bool:
    """Whether a stamp from today can be taken as the closing prices."""
    if as_of.date() != now.date():
        return False

    return as_of.time() >= _MARKET_CLOSE or now.time() >= _CLOSE_STAMP_DEADLINE


def _print_chat_ids() -> None:
    config = Config.load(require_chat_id=False)

    with TelegramNotifier(config.bot_token) as bot:
        chats = bot.discover_chats()

    if not chats:
        print('No chats yet. Send your bot a message in Telegram, then re-run this.')
        return

    for chat_id, label in chats:
        print(f"  {chat_id}\t{label}")

    print('\nPut TELEGRAM_CHAT_ID=<id> in .env')


if __name__ == '__main__':
    sys.exit(main())