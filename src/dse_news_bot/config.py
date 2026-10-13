from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from dse_news_bot.exceptions import ConfigError

_PORTFOLIO_KEY = 'PORTFOLIO'
_BOT_TOKEN_KEY = 'TELEGRAM_BOT_TOKEN'
_CHAT_ID_KEY = 'TELEGRAM_CHAT_ID'
_STATE_PATH_KEY = 'STATE_PATH'

_DEFAULT_STATE_PATH = Path('.state/sent.json')


@dataclass(frozen=True)
class Config:
    portfolio: frozenset[str]
    bot_token: str
    chat_id: str
    state_path: Path

    @classmethod
    def load(cls, require_chat_id: bool = True, require_bot_token: bool = True) -> Config:
        """Read settings from the environment, falling back to a local ``.env``.

        ``require_chat_id`` is off for the ``--chat-id`` bootstrap, which by
        definition runs before the chat id is known. ``require_bot_token`` is
        off for console-only modes that never talk to Telegram.
        """
        load_dotenv()

        chat_id = os.getenv(_CHAT_ID_KEY, '').strip()

        if require_chat_id and not chat_id:
            raise ConfigError(_missing(_CHAT_ID_KEY, 'run `python main.py --chat-id` to find it'))

        return cls(
            portfolio=_read_portfolio(),
            bot_token=(
                _read_required(_BOT_TOKEN_KEY, 'get one from @BotFather on Telegram')
                if require_bot_token
                else os.getenv(_BOT_TOKEN_KEY, '').strip()
            ),
            chat_id=chat_id,
            state_path=Path(os.getenv(_STATE_PATH_KEY) or _DEFAULT_STATE_PATH),
        )


def _read_portfolio() -> frozenset[str]:
    raw = _read_required(_PORTFOLIO_KEY, 'a comma-separated list of trading codes')
    trackers = frozenset(code.strip().upper() for code in raw.split(',') if code.strip())

    if not trackers:
        raise ConfigError(f"{_PORTFOLIO_KEY} holds no trading codes")

    return trackers


def _read_required(key: str, hint: str) -> str:
    value = os.getenv(key, '').strip()

    if not value:
        raise ConfigError(_missing(key, hint))

    return value


def _missing(key: str, hint: str) -> str:
    return f"{key} is not set - add it to your .env ({hint})"
