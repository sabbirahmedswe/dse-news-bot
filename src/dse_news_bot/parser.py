from bs4 import BeautifulSoup, Tag
from dse_news_bot.models import News

# def parse(text: str) -> list[Tag]:
#     content_rows: list[Tag] = []
    
#     soup = BeautifulSoup(text, 'html.parser')
#     news_table = soup.find('table', class_='table-news')

#     for child in news_table.children:
#         if _skip_row(child):
#             continue
        
#         content_rows.append(child)

#     return content_rows

# _TABLE_NEWS_CLASS = 'table-news'

def parse_news_page(html: str) -> list[News]:
    soup = BeautifulSoup(html, 'html.parser')
    news_table = soup.table(class_=_TABLE_NEWS_CLASS)

    print(news_table)

    return []

# def _skip_row(tag) -> bool:
#     return not isinstance(tag, Tag) or _is_separator_row(tag)

# def _is_separator_row(tag) -> bool:
#     return 'colspan' in tag.th.attrs