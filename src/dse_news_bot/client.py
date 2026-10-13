from __future__ import annotations

from types import TracebackType

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import datetime as dt

from dse_news_bot.exceptions import FetchError

_NEWS_URL = 'https://old.dsebd.org/old_news.php'
_NEWS_CRITERIA = '4'
_ARCHIVE_TYPE = 'news'

_PRICES_URL = 'https://old.dsebd.org/latest_share_price_scroll_l.php'

_MAX_RETRIES = 4
_BACKOFF_FACTOR = 0.5
_RETRY_STATUSES = (429, 500, 502, 503, 504)

class DseNewsClient:
    def __init__(self) -> None:
        self._session = self._build_session()

    def fetch(self) -> str:
        params = {
            'startDate': self._today(),
            'endDate': self._today(),
            'criteria': _NEWS_CRITERIA,
            'archive': _ARCHIVE_TYPE
        }

        return self._get(_NEWS_URL, 'news', params=params)

    def fetch_prices(self) -> str:
        """Fetch the latest share price table for every listed ticker."""
        return self._get(_PRICES_URL, 'share prices')

    def _get(self, url: str, what: str, params: dict[str, str] | None = None) -> str:
        try:
            response = self._session.get(url, params=params)
            response.raise_for_status()
        except Exception as err:
            raise FetchError(f"Unable to fetch {what} from DSE, {err=}") from err

        return response.text

    def _today(self) -> str:
        return dt.date.today().isoformat()

    def __enter__(self) -> DseNewsClient:
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
            allowed_methods=frozenset({'GET'}),
            raise_on_status=False,
        )

        session = Session()
        session.mount('https://', HTTPAdapter(max_retries=retry))
        session.mount('http://', HTTPAdapter(max_retries=retry))

        return session

   
