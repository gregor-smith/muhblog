import io
import math as maths

import flask
import pkg_resources
from htmlmin.minify import html_minify


class Paginator:
    def __init__(self, query, current_page):
        self.query = query
        self.current_page = current_page
        self.total_entries = self.query.count()

    def get_entries(self, page=None):
        return self.query.paginate(
            page or self.current_page,
            flask.current_app.config['BLOG_ENTRIES_PER_PAGE']
        )

    def total_pages(self):
        per_page = flask.current_app.config['BLOG_ENTRIES_PER_PAGE']
        return maths.ceil(self.total_entries / per_page)

    def has_previous_page(self):
        return self.current_page != 1

    def has_next_page(self):
        return self.current_page != self.total_pages()

    def page_link_group(self, start=1, group_size=5):
        end = self.total_pages()

        if end - start <= group_size:
            return range(start, end + 1)

        padding = group_size // 2
        group_start = self.current_page - padding
        group_end = self.current_page + padding

        if group_start < start:
            end_extra = start - group_start
            group_start = start
        else:
            end_extra = 0

        if group_end > end:
            start_extra = (0 if end_extra != 0 else (group_end - end))
            group_end = end
        else:
            start_extra = 0

        return range(group_start - start_extra, group_end + end_extra + 1)


def send_configurable_file(config_key, mimetype, fallback):
    path = flask.current_app.config[config_key]
    if path is None:
        byts = pkg_resources.resource_string('muhblog', fallback)
    else:
        with open(path, mode='rb') as file:
            byts = file.read()
    return flask.send_file(io.BytesIO(byts), mimetype=mimetype)


def render_template(*args, **kwargs):
    html = flask.render_template(*args, **kwargs)
    return html_minify(html)
