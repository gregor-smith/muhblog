import re
import time
import logging
import pathlib
import datetime
import functools
import threading
import configparser

import click
import flask
import slugify
import markdown

DATE_FORMAT = '%Y-%m-%d %H:%M'
MAX_TITLE_LENGTH = 100
MAX_CACHE_SIZE = 256

app = flask.Flask(__name__)

class Entry:
    formatting_regex = re.compile(r'\[([a-z]+)(?: (.+?))?\](.+?)\[/([a-z]+)\]', re.DOTALL)

    def __init__(self, path):
        self.parser = configparser.ConfigParser(interpolation=None)
        self.path = path
        self.reload()

    def __repr__(self):
        return '{}(path={!r})'.format(type(self).__name__, self.path)

    def __lt__(self, other):
        try:
            return self.datetime_written < other.datetime_written
        except (AttributeError, TypeError):
            return NotImplemented

    def reload(self):
        self.parser.clear()
        self.parser.read(str(self.path), encoding='utf-8')

        entry = self.parser['entry']

        self.title = entry['title']
        self.markdown_text = entry['text']
        self.datetime_written = datetime.datetime.strptime(entry['date'], DATE_FORMAT)
        self.timestamp_modified = self.path.stat().st_mtime
        self.is_hidden = self.parser.getboolean('entry', 'is_hidden', fallback=True)

    @staticmethod
    @functools.lru_cache(MAX_CACHE_SIZE)
    def _slugify(text):
        return slugify.slugify(text, max_length=MAX_TITLE_LENGTH)

    def title_slug(self):
        return self._slugify(self.title)

    @staticmethod
    def formatting_replacer(match):
        tag_one, replacement, text, tag_two = match.groups()
        if tag_one != tag_two:
            return match.string
        if tag_one == 'hidden':
            return replacement or ''
        return '<span class="spoiler">{}</span>'.format(text)

    @classmethod
    @functools.lru_cache(MAX_CACHE_SIZE)
    def _format_text(cls, text):
        return cls.formatting_regex.sub(cls.formatting_replacer, text)

    def formatted_text(self):
        return self._format_text(self.markdown_text)

    @staticmethod
    @functools.lru_cache(MAX_CACHE_SIZE)
    def _markdown(text):
        return flask.Markup(markdown.markdown(text))

    def html_text(self):
        return self._markdown(self.formatted_text())

class Archive(dict):
    def __init__(self, path, show_hidden):
        super().__init__()
        self.path = pathlib.Path(path)
        self.show_hidden = show_hidden

        self.reload()

    __repr__ = Entry.__repr__

    def reload(self):
        for path in self.path.glob('*.ini'):
            if path.is_file():
                if path in self:
                    entry = self[path]
                    if path.stat().st_mtime > entry.timestamp_modified:
                        app.logger.info('entry file modified, reloading - %r', path)
                        try:
                            entry.reload()
                        except Exception:
                            app.logger.exception('reload threw exception, removing - %r', path)
                            del self[path]
                    else:
                        app.logger.debug('entry file has not been modified - %r', path)
                else:
                    app.logger.debug('adding new entry - %r', path)
                    try:
                        self[path] = Entry(path)
                    except Exception:
                        app.logger.exception('exception creating entry, skipping - %r', path)
        for path in list(self.keys()):
            if not path.exists():
                app.logger.info('entry no longer exists, removing - %r', path)
                del self[path]

    def reloader_thread_worker(self, interval):
        while True:
            time.sleep(interval)
            self.reload()

    @staticmethod
    def date_comparison_function(attribute, value):
        return lambda entry: getattr(entry.datetime_written, attribute) == value

    def default_conditions(self, **kwargs):
        if not self.show_hidden:
            yield lambda entry: not entry.is_hidden
        for attribute in ['year', 'month', 'day']:
            if attribute in kwargs:
                yield self.date_comparison_function(attribute, kwargs[attribute])

    def filter(self, *additional_conditions, **kwargs):
        conditions = [*self.default_conditions(**kwargs), *additional_conditions]
        for entry in self.values():
            if all(condition(entry) for condition in conditions):
                yield entry

@app.route('/archive')
@app.route('/<int:year>')
@app.route('/<int:year>/<int:month>')
@app.route('/<int:year>/<int:month>/<int:day>')
def archive(**kwargs):
    entries = list(app.archive.filter(**kwargs))
    if not entries:
        flask.abort(404)
    entries.sort(reverse=True)
    return flask.render_template('archive.html', title='Archive', entries=entries)

@app.route('/<int:year>/<int:month>/<int:day>/<title_slug>')
def entry(title_slug, **kwargs):
    entries = app.archive.filter(lambda entry: entry.title_slug() == title_slug, **kwargs)
    try:
        entry = next(entries)
    except StopIteration:
        flask.abort(404)
    return flask.render_template('entry.html', title=entry.title, entry=entry)

@app.route('/robots.txt')
def robots():
    return flask.send_from_directory(app.static_folder, 'robots.txt')

def render_error_template(code, name, image):
    return flask.render_template('error.html', title='{} {}'.format(code, name), image=image), code

@app.errorhandler(404)
def error_404(error):
    return render_error_template(404, 'Not Found', '/static/404.png')
@app.errorhandler(403)
def error_403(error):
    return render_error_template(403, 'Forbidden', '/static/403.jpg')
@app.errorhandler(500)
def error_500(error):
    return render_error_template(500, 'Internal Server Error', '/static/500.jpg')

@click.command()
@click.option('--archive-path', envvar='BLOG_ARCHIVE_PATH',
              type=click.Path(file_okay=False, writable=True))
@click.option('--host')
@click.option('--port', type=int, default=9001, show_default=True)
@click.option('--debug', is_flag=True, show_default=True)
@click.option('--show-hidden', is_flag=True, show_default=True)
@click.option('--reload-interval', type=int, default=300, show_default=True)
def main(archive_path, host, port, debug, show_hidden, reload_interval):
    if archive_path is None:
        raise click.BadParameter("either '--archive-path' must be provided "
                                 "or the 'BLOG_ARCHIVE_PATH' environment variable must be set")

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s %(levelname)s] %(message)s'))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG if debug else logging.INFO)

    app.archive = Archive(archive_path, show_hidden)
    app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True

    archive_reloader_thread = threading.Thread(target=app.archive.reloader_thread_worker,
                                               kwargs={'interval': reload_interval},
                                               name='archive_reloader', daemon=True)
    archive_reloader_thread.start()
    app.run(host=host, port=port, debug=debug)
