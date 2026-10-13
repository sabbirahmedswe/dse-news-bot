from __future__ import annotations

import logging
import os
import re
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

_LOG_PATH_KEY = 'LOG_PATH'
_LOG_LEVEL_KEY = 'LOG_LEVEL'

_DEFAULT_LOG_PATH = Path('.logs/dse-news-bot.log')
_DEFAULT_LOG_LEVEL = 'INFO'

_RETENTION_DAYS = 14

_FILE_FORMAT = '%(asctime)s %(levelname)-8s %(name)s: %(message)s'
_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

_CONSOLE_FORMAT = '%(message)s'

# requests/urllib3 put the whole URL in their records, and a Telegram URL carries
# the bot token
_NOISY_LOGGERS = ('urllib3', 'requests')

# a Telegram token is "<bot id>:<secret>"
_TOKEN_PATTERN = re.compile(r'bot\d+:[A-Za-z0-9_-]{20,}')
_TOKEN_REPLACEMENT = 'bot<redacted>'

_MARKER = '_dse_news_bot'


def setup_logging() -> None:
    """Send log records to the console and to a daily-rotated file.

    Reads ``LOG_PATH`` and ``LOG_LEVEL`` from the environment directly rather
    than from :class:`~dse_news_bot.config.Config`: loading the config is itself
    a step that fails, and those failures belong in the log file.
    """
    root = logging.getLogger()

    if any(getattr(handler, _MARKER, False) for handler in root.handlers):
        return

    load_dotenv()

    root.setLevel(_read_level())

    _add(root, _console_handler())

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    path = Path(os.getenv(_LOG_PATH_KEY) or _DEFAULT_LOG_PATH)
    handler = _file_handler(path)

    if handler is None:
        logging.getLogger(__name__).warning(
            "Not logging to %s - console only for this run", path
        )
        return

    _add(root, handler)


class _RedactTokens(logging.Filter):
    """Strip bot tokens out of a record before any handler writes it.

    urllib3 logs the request path when it retries, and every Telegram call has
    the token in its URL - so a single 429 would otherwise put the token on disk.
    Matching the token's shape avoids handing the real one to the log layer.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _TOKEN_PATTERN.sub(_TOKEN_REPLACEMENT, message)

        if redacted != message:
            record.msg = redacted
            record.args = ()

        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)

        if record.exc_text:
            record.exc_text = _TOKEN_PATTERN.sub(_TOKEN_REPLACEMENT, record.exc_text)

        if record.stack_info:
            record.stack_info = _TOKEN_PATTERN.sub(_TOKEN_REPLACEMENT, record.stack_info)

        return True


def _file_handler(path: Path) -> logging.Handler | None:
    """Build the rotating file handler, or ``None`` if the path is unusable.

    A wrong ``LOG_PATH`` is the same footgun as a wrong ``STATE_PATH`` under the
    scheduler, where the working directory is ``C:\\Windows\\System32``. Losing
    the log file is worth a warning; it is not worth losing the run.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        handler = TimedRotatingFileHandler(
            path,
            when='midnight',
            backupCount=_RETENTION_DAYS,
            encoding='utf-8',
        )
    except OSError:
        return None

    handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT))

    return handler


def _console_handler() -> logging.Handler:
    # stderr, so a command's own output on stdout (the market update) stays clean
    # when piped
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))

    return handler


def _add(root: logging.Logger, handler: logging.Handler) -> None:
    handler.addFilter(_RedactTokens())
    setattr(handler, _MARKER, True)
    root.addHandler(handler)


def _read_level() -> int:
    name = (os.getenv(_LOG_LEVEL_KEY) or _DEFAULT_LOG_LEVEL).strip().upper()
    level = logging.getLevelNamesMapping().get(name)

    return level if isinstance(level, int) else logging.INFO
