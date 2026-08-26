from __future__ import annotations

import html
import time
from types import TracebackType
from typing import Any

from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from dse_news_bot.exceptions import NotifyError
from dse_news_bot.models import News

_API_BASE = 'https://api.telegram.org/bot{token}/{method}'

# Telegram rejects anything longer, and allows roughly one message per second
# per chat.
_MAX_MESSAGE_LEN = 4096
_SEND_INTERVAL = 1.0

_MAX_RETRIES = 4
_BACKOFF_FACTOR = 0.5
_RETRY_STATUSES = (429, 500, 502, 503, 504)


class TelegramNotifier:
    def __init__(self, token: str) -> None:
        self._token = token
        self._session = self._build_session()

    def send_news(self, chat_id: str, news: News) -> None:
        """Deliver one news item, splitting it if it exceeds Telegram's limit."""
        for chunk in _split(_format(news)):
            self._call('sendMessage', json={
                'chat_id': chat_id,
                'text': chunk,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True,
            })
            time.sleep(_SEND_INTERVAL)

    def discover_chats(self) -> list[tuple[str, str]]:
        """Return ``(chat_id, label)`` for every chat that has messaged the bot."""
        payload = self._call('getUpdates', http_method='GET')
        chats: dict[str, str] = {}

        for update in payload.get('result', []):
            chat = _chat_of(update)

            if chat is None:
                continue

            chats.setdefault(str(chat.get('id')), _label(chat))

        return list(chats.items())

    def _call(self, method: str, json: dict[str, Any] | None = None, http_method: str = 'POST') -> dict[str, Any]:
        url = _API_BASE.format(token=self._token, method=method)

        try:
            response = self._session.request(http_method, url, json=json)
        except Exception as err:
            raise NotifyError(f"Unable to reach Telegram, {err=}") from err

        return _unwrap(response, method)

    def __enter__(self) -> TelegramNotifier:
        return self

    def _close(self) -> None:
        self._session.close()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._close()

    def _build_session(self) -> Session:
        retry = Retry(
            total=_MAX_RETRIES,
            backoff_factor=_BACKOFF_FACTOR,
            status_forcelist=_RETRY_STATUSES,
            # POST too, unlike the news client - Telegram returns Retry-After on
            # 429 and urllib3 honours it.
            allowed_methods=frozenset({'GET', 'POST'}),
            raise_on_status=False,
        )

        session = Session()
        session.mount('https://', HTTPAdapter(max_retries=retry))

        return session


def _unwrap(response: Response, method: str) -> dict[str, Any]:
    """Return the API payload, surfacing Telegram's own error description.

    Its wording - "chat not found", "Unauthorized" - is the fastest way to tell
    a bad token from a bad chat id.
    """
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.ok and payload.get('ok'):
        return payload

    reason = payload.get('description') or response.text.strip() or 'no response body'

    raise NotifyError(f"Telegram {method} failed ({response.status_code}): {reason}")


def _format(news: News) -> str:
    """Render a news item as Telegram HTML.

    HTML rather than MarkdownV2: it only needs ``&``, ``<`` and ``>`` escaped,
    where MarkdownV2 would need escaping for characters DSE notices use
    constantly - ``.``, ``-``, ``(``, ``%``.
    """
    # quote=False: only & < > are special in Telegram's HTML mode, and DSE
    # notices are full of apostrophes.
    tracker = html.escape(news.tracker, quote=False)
    title = html.escape(news.title, quote=False)
    content = html.escape(news.content, quote=False)

    return f"#{tracker}\n<b>{title}</b>\n\n{content}"


def _split(text: str) -> list[str]:
    """Break text into sendable chunks, preferring a line or word boundary."""
    chunks: list[str] = []

    while len(text) > _MAX_MESSAGE_LEN:
        window = text[:_MAX_MESSAGE_LEN]
        cut = max(window.rfind('\n'), window.rfind(' '))

        if cut <= 0:
            cut = _MAX_MESSAGE_LEN

        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()

    chunks.append(text)

    return chunks


def _chat_of(update: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the chat out of whichever update kind Telegram sent."""
    for key in ('message', 'edited_message', 'channel_post', 'my_chat_member'):
        chat = update.get(key, {}).get('chat')

        if isinstance(chat, dict):
            return chat

    return None


def _label(chat: dict[str, Any]) -> str:
    name = chat.get('title') or ' '.join(
        part for part in (chat.get('first_name'), chat.get('last_name')) if part
    )
    username = chat.get('username')

    if username:
        name = f"{name} (@{username})".strip()

    return f"{name or 'unnamed'} [{chat.get('type', 'unknown')}]"
