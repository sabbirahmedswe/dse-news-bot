from __future__ import annotations

import logging
import sys

from dse_news_bot.config import Config
from dse_news_bot.exceptions import ConfigError, FetchError, NotifyError, ParseError
from dse_news_bot.client import DseNewsClient
from dse_news_bot.logs import setup_logging
from dse_news_bot.notifier import TelegramNotifier
from dse_news_bot.parser import parse_news_page
from dse_news_bot.state import SentLog

_CHAT_ID_FLAG = '--chat-id'

logger = logging.getLogger(__package__)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    setup_logging()

    try:
        if _CHAT_ID_FLAG in argv:
            _print_chat_ids()
        else:
            _send_todays_news()
    except (ConfigError, FetchError, ParseError, NotifyError) as err:
        logger.error('%s', err)
        return 1
    except Exception:
        logger.exception('Unexpected failure')
        return 1

    return 0


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