from app.scraper import get_html
import app.parser as parser
from app.extractor import extract_all

def main():
    text: str = get_html()

    if text is None:
        return

    contents = parser.parse(text)
    all_news = extract_all(contents)

if __name__ == '__main__':
    main()



    