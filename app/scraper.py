import requests
import datetime as dt

DSE_NEWS_BASE_URL = "https://www.dsebd.org/old_news.php"

def get_html() -> str:
    try:   
        req = requests.get(DSE_NEWS_BASE_URL, params=_params())
        if req.status_code != 200:
            return None
    
        return req.text
    except Exception as err:
        print(f'Unexpected {err=}, {type(err)=}')
        return None

def _params() -> dict:
    return {
        'startDate': _today_isoformat(),
        'endDate': _today_isoformat(),
        'criteria': 4,
        'archive': 'news'
    }

def _today_isoformat() -> str:
    return dt.date.today().isoformat()
