import math as maths
from typing import Iterable

from flask import Response, render_template, make_response
from peewee import SelectQuery
from htmlmin.minify import html_minify

from .models import Entry

PAGE_GROUP_SIZE = 5
ENTRIES_PER_PAGE = 10


class Paginator:
    query: SelectQuery
    current_page: int

    def __init__(self, query: SelectQuery, current_page: int) -> None:
        self.query = query
        self.current_page = current_page

    def get_entries(self) -> Iterable[Entry]:
        return self.query.paginate(self.current_page, ENTRIES_PER_PAGE) \
            .iterator()

    def get_total_pages(self) -> int:
        return maths.ceil(self.query.count() / ENTRIES_PER_PAGE)

    def has_previous_page(self) -> bool:
        return self.current_page != 1

    def has_next_page(self) -> bool:
        return self.current_page != self.get_total_pages()

    def page_number_group(self) -> Iterable[int]:
        padding = PAGE_GROUP_SIZE // 2
        start_page = self.current_page - padding
        end_page = self.current_page + padding

        total_pages = self.get_total_pages()

        if start_page < 1 and end_page > total_pages:
            start_page = 1
            end_page = total_pages
        else:
            if start_page < 1:
                difference = 1 - start_page
                start_page += difference
                end_page += difference
            if end_page > total_pages:
                difference = end_page - total_pages
                end_page -= difference
                start_page -= difference
                if start_page < 1:
                    start_page = 1

        return range(start_page, end_page + 1)


def template_response(*args, status_code: int = 200, **kwargs) -> Response:
    html = render_template(*args, **kwargs)
    html = html_minify(html)
    return make_response(html, status_code)
