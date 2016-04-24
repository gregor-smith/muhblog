import re
import time
import logging
import pathlib
import datetime
import threading

import click
import flask
import slugify
import markdown
import markdown.extensions.meta

DATE_FORMAT = '%Y-%m-%d %H:%M'
MAX_TITLE_LENGTH = 100

app = flask.Flask(__name__)

class HiddenTagPattern(markdown.postprocessors.Postprocessor):
    regex = re.compile(r'\[hidden(?: (.+?))?\](.+?)\[/hidden\]', re.DOTALL)

    def __init__(self, show_hidden, *args, **kwargs):
        self.show_hidden = show_hidden
        super().__init__(*args, **kwargs)

    def replacer(self, match):
        replacement, text = match.groups()
        return text if self.show_hidden else (replacement or '')

    def run(self, text):
        return self.regex.sub(self.replacer, text)

class HiddenTagExtension(markdown.Extension):
    def __init__(self, show_hidden, **kwargs):
        self.show_hidden = show_hidden
        super().__init__(**kwargs)

    def extendMarkdown(self, md, md_globals):
        md.postprocessors[type(self).__name__] = HiddenTagPattern(self.show_hidden)

class SpoilerTagPattern(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        element = markdown.util.etree.Element('span')
        element.set('class', 'spoiler')
        element.text = markdown.util.AtomicString(match.group('text'))
        return element

class SpoilerTagExtension(markdown.Extension):
    regex_pattern = r'\[spoiler\](?P<text>.+?)\[/spoiler\]'

    def extendMarkdown(self, md, md_globals):
        md.inlinePatterns[type(self).__name__] = SpoilerTagPattern(self.regex_pattern, md)

class Entry:
    formatting_regex = re.compile(r'\[([a-z]+)(?: (.+?))?\](.+?)\[/([a-z]+)\]', re.DOTALL)

    def __init__(self, archive, path):
        self.archive = archive
        self.path = path

        self.reload()

    def __repr__(self):
        return '{}(path={!r})'.format(type(self).__name__, self.path)

    def __lt__(self, other):
        try:
            return self.datetime_written < other.datetime_written
        except (AttributeError, TypeError):
            return NotImplemented

    @staticmethod
    def string_to_boolean(string):
        string = string.lower()
        if string in {'true', 'yes', 'aye', '1'}:
            return True
        if string in {'false', 'no', 'naw', '0'}:
            return False
        raise ValueError(string)

    def reload(self):
        self.parser = markdown.Markdown(extensions=[markdown.extensions.meta.MetaExtension(),
                                                    HiddenTagExtension(self.archive.show_hidden),
                                                    SpoilerTagExtension()])

        self.text = flask.Markup(self.parser.convert(self.path.read_text(encoding='utf-8')))
        self.title = self.parser.Meta['title'][0]
        self.title_slug = slugify.slugify(self.title, max_length=100)
        self.datetime_written = datetime.datetime.strptime(self.parser.Meta['date'][0],
                                                           DATE_FORMAT)
        self.timestamp_modified = self.path.stat().st_mtime
        self.tags = {tag: slugify.slugify(tag) for tag in self.parser.Meta['tags']}
        self.is_hidden = (self.string_to_boolean(self.parser.Meta['is_hidden'][0])
                          if 'is_hidden' in self.parser.Meta else True)

class Archive(dict):
    def __init__(self, app, path, show_hidden, reload_interval):
        super().__init__()
        self.app = app
        self.path = pathlib.Path(path)
        self.show_hidden = show_hidden
        self.reload_interval = reload_interval

        self.reload_finish_event = threading.Event()
        self.reload_finish_event.set()
        self.reload_thread = threading.Thread(target=self.reload_thread_worker, daemon=True)
        self.reload_thread.start()

    __repr__ = Entry.__repr__

    def reload_thread_worker(self):
        while True:
            self.reload()
            time.sleep(self.reload_interval)

    def reload(self):
        self.reload_finish_event.clear()

        for path in self.path.glob('*.md'):
            if path.is_file():
                if path in self:
                    entry = self[path]
                    if path.stat().st_mtime > entry.timestamp_modified:
                        self.app.logger.info('entry file modified, reloading - %r', path)
                        try:
                            entry.reload()
                        except Exception:
                            self.app.logger.exception('reload threw exception, removing - %r', path)
                            del self[path]
                    else:
                        self.app.logger.debug('entry file has not been modified - %r', path)
                else:
                    self.app.logger.debug('adding new entry - %r', path)
                    try:
                        self[path] = Entry(self, path)
                    except Exception:
                        self.app.logger.exception('exception creating entry, skipping - %r', path)

        for path in list(self.keys()):
            if not path.exists():
                self.app.logger.info('entry no longer exists, removing - %r', path)
                del self[path]

        self.reload_finish_event.set()

    @staticmethod
    def date_condition(attribute, value):
        return lambda entry: getattr(entry.datetime_written, attribute) == value

    def filter(self, *conditions):
        if not self.show_hidden:
            conditions = [lambda entry: not entry.is_hidden, *conditions]
        for entry in self.values():
            if all(condition(entry) for condition in conditions):
                yield entry

@app.route('/archive')
@app.route('/tag/<tag_slug>')
@app.route('/<int:year>')
@app.route('/<int:year>/<int:month>')
@app.route('/<int:year>/<int:month>/<int:day>')
def archive(tag_slug=None, year=None, month=None, day=None):
    app.archive.reload_finish_event.wait()

    conditions = []
    if year is not None:
        title_parts = [str(year)]
        conditions.append(app.archive.date_condition('year', year))
        if month is not None:
            title_parts.append('{:0>2}'.format(month))
            conditions.append(app.archive.date_condition('month', month))
            if day is not None:
                title_parts.append('{:0>2}'.format(day))
                conditions.append(app.archive.date_condition('day', day))
        title = '/'.join(reversed(title_parts))
    elif tag_slug is not None:
        title = tag_slug
        conditions.append(lambda entry: tag_slug in entry.tags.values())
    else:
        title = 'Archive'

    entries = list(app.archive.filter(*conditions))
    if not entries:
        flask.abort(404)
    entries.sort(reverse=True)

    return flask.render_template('archive.html', title=title, entries=entries)

@app.route('/<int:year>/<int:month>/<int:day>/<title_slug>')
def entry(title_slug, **kwargs):
    app.archive.reload_finish_event.wait()

    conditions = (app.archive.date_condition(attribute, kwargs[attribute])
                  for attribute in ['year', 'month', 'day'])
    entries = app.archive.filter(*conditions, lambda entry: entry.title_slug == title_slug)
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

    app.archive = Archive(app, archive_path, show_hidden, reload_interval)
    app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True
    app.run(host=host, port=port, debug=debug)
