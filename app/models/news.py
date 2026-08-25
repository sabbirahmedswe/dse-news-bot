class News:
    def __init__(self, tracker='', title='', content='', dt='') -> None:
        self.tracker = tracker
        self.title = title
        self.content = content
        self.published_on = dt

    def __repr__(self):
        return '{}\n\n{}\n\n'.format(self.tracker,  self.content)