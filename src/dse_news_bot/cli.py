from __future__ import annotations

import sys

from dse_news_bot.config import Config
from dse_news_bot.exceptions import ConfigError, FetchError, NotifyError, ParseError
from dse_news_bot.client import DseNewsClient
from dse_news_bot.notifier import TelegramNotifier
from dse_news_bot.parser import parse_news_page
from dse_news_bot.state import SentLog

_CHAT_ID_FLAG = '--chat-id'


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    try:
        if _CHAT_ID_FLAG in argv:
            _print_chat_ids()
        else:
            _send_todays_news()
    except (ConfigError, FetchError, ParseError, NotifyError) as err:
        print(err, file=sys.stderr)
        return 1

    return 0


def _send_todays_news() -> None:
    config = Config.load()

    with DseNewsClient() as client:
        html = client.fetch()

    sent = SentLog.load(config.state_path)
    pending = [
        news for news in parse_news_page(html)
        if news.tracker.upper() in config.portfolio and not sent.has(news)
    ]

    if not pending:
        print('No new news for your portfolio.')
        return

    try:
        with TelegramNotifier(config.bot_token) as bot:
            for news in pending:
                bot.send_news(config.chat_id, news)
                # only after the send, so a failure is retried next run
                sent.mark(news)
                print(f"Sent {news.tracker}: {news.title}")
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
    raise sys.exit(main())