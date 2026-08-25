from bs4 import Tag
from .models.news import News

def extract_all(contents: list[Tag]) -> list[News]:
    result: list[News] = []

    for i in range(0, len(contents), 4):
        
        tracker: str = contents[i].td.string
        title: str = contents[i + 1].td.string
        content: str = contents[i + 2].td.string
        date: str = contents[i + 3].td.string
        
        news = News(tracker, title, content, date)
        result.append(news)

    return result