import logging
import pathlib
from datetime import datetime

import click
import flask
import markdown
import flask.ext.frozen
import markdown.extensions.meta
from slugify import slugify

app = flask.Flask(__name__)
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*']
app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True

formatter = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
app.logger.addHandler(handler)

freezer = flask.ext.frozen.Freezer(app)

class SpoilerTagPattern(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        element = markdown.util.etree.Element('span')
        element.set('class', 'spoiler')
        element.text = markdown.util.AtomicString(match.group('text'))
        return element

class SpoilerTagExtension(markdown.Extension):
    regex_pattern = r'\[spoiler\](?P<text>.+?)\[/spoiler\]'

    def extendMarkdown(self, md, md_globals):
        md.inlinePatterns[type(self).__name__] \
            = SpoilerTagPattern(self.regex_pattern, md)

class Entry:
    def __init__(self, path):
        self.path = path

        parser = markdown.Markdown(
            extensions=[markdown.extensions.meta.MetaExtension(),
                        SpoilerTagExtension()]
        )

        self.text = flask.Markup(
            parser.convert(self.path.read_text(encoding='utf-8'))
        )
        self.title = parser.Meta['title'][0]
        self.title_slug = slugify(self.title, max_length=100)
        self.date_written = datetime.strptime(parser.Meta['date'][0],
                                                  '%Y-%m-%d %H:%M')
        self.tags = {tag: slugify(tag) for tag in parser.Meta['tags']}

    def __repr__(self):
        return '{}(path={!r})'.format(type(self).__name__, self.path)

    def __lt__(self, other):
        try:
            return self.date_written < other.date_written
        except (AttributeError, TypeError):
            return NotImplemented

class Archive(dict):
    def __init__(self, path):
        super().__init__()
        self.path = path

        for path in self.path.glob('*.md'):
            if path.is_file():
                self[path] = Entry(path)

    __repr__ = Entry.__repr__

    @staticmethod
    def date_condition(attr, value):
        return lambda entry: getattr(entry.date_written, attr) == value

    def filter(self, *conditions):
        for entry in self.values():
            if all(condition(entry) for condition in conditions):
                yield entry

@app.route('/')
@app.route('/tag/<tag_slug>/')
@app.route('/<int:year>/')
@app.route('/<int:year>/<int:month>/')
@app.route('/<int:year>/<int:month>/<int:day>/')
def archive_view(tag_slug=None, year=None, month=None, day=None):
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

@app.route('/<int:year>/<int:month>/<int:day>/<title_slug>/')
def entry_view(title_slug, **kwargs):
    conditions = (app.archive.date_condition(attribute, kwargs[attribute])
                  for attribute in ['year', 'month', 'day'])
    title_condition = lambda entry: entry.title_slug == title_slug
    entries = app.archive.filter(*conditions, title_condition)
    try:
        entry = next(entries)
    except StopIteration:
        flask.abort(404)
    return flask.render_template('entry.html', title=entry.title, entry=entry)

@app.route('/robots.txt')
def robots_txt_view():
    return flask.send_from_directory(app.static_folder, 'robots.txt',
                                     mimetype='text/plain')

def render_error_template(code, name, image):
    return flask.render_template('error.html', image=image,
                                 title='{} {}'.format(code, name)), code

@app.errorhandler(404)
def error_404_view(error):
    return render_error_template(404, 'Not Found', '404.png')
@app.errorhandler(403)
def error_403_view(error):
    return render_error_template(403, 'Forbidden', '403.jpg')
@app.errorhandler(500)
def error_500_view(error):
    return render_error_template(500, 'Internal Server Error', '500.jpg')

@click.group()
@click.option('--archive-path', envvar='BLOG_ARCHIVE_PATH',
              type=click.Path(file_okay=False, writable=True))
def main(archive_path):
    if archive_path is None:
        raise click.BadParameter("either '--archive-path' must be provided "
                                 "or the 'BLOG_ARCHIVE_PATH' environment "
                                 'variable must be set')
    app.archive = Archive(pathlib.Path(archive_path))

@main.command()
def freeze():
    freezer.freeze()

@main.command()
@click.option('--host')
@click.option('--port', type=int, default=9001, show_default=True)
@click.option('--debug', is_flag=True)
def run(host, port, debug):
    app.logger.setLevel('DEBUG' if debug else 'INFO')
    app.run(host=host, port=port, debug=debug)
