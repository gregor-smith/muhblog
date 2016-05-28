import os
import pathlib
import subprocess
from datetime import datetime

import click
import flask
import markdown
import flask.ext.frozen
import markdown.extensions.meta
from slugify import slugify

app = flask.Flask(__name__)
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*']
app.config['FREEZER_DESTINATION'] = str(pathlib.Path('freeze').absolute())
app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True

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

markdown_parser = markdown.Markdown(
    extensions=[markdown.extensions.meta.MetaExtension(),
                SpoilerTagExtension()]
)

class Entry:
    def __init__(self, path):
        self.path = path

        self.text = flask.Markup(
            markdown_parser.convert(self.path.read_text(encoding='utf-8'))
        )
        self.title = markdown_parser.Meta['title'][0]
        self.title_slug = slugify(self.title, max_length=100)
        self.date_written = datetime.strptime(markdown_parser.Meta['date'][0],
                                              '%Y-%m-%d %H:%M')
        self.tags = {slugify(tag): tag for tag in markdown_parser.Meta['tags']}

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
        self.tags = {}

        for path in self.path.glob('*.md'):
            if path.is_file():
                self[path] = entry = Entry(path)
                self.tags.update(entry.tags)

    __repr__ = Entry.__repr__

    def filter(self, *conditions):
        for entry in self.values():
            if all(condition(entry) for condition in conditions):
                yield entry

def date_condition(attr, value):
    return lambda entry: getattr(entry.date_written, attr) == value

@app.route('/')
@app.route('/tag/<tag_slug>/')
@app.route('/<year>/')
@app.route('/<year>/<month>/')
@app.route('/<year>/<month>/<day>/')
def archive_view(tag_slug=None, year=None, month=None, day=None):
    conditions = []
    if year is not None:
        title_parts = [year]
        conditions.append(date_condition('year', int(year)))
        if month is not None:
            title_parts.append(month)
            conditions.append(date_condition('month', int(month)))
            if day is not None:
                title_parts.append(day)
                conditions.append(date_condition('day', int(day)))
        title = '/'.join(reversed(title_parts))
    elif tag_slug is not None:
        title = app.archive.tags[tag_slug]
        conditions.append(lambda entry: tag_slug in entry.tags)
    else:
        title = None

    entries = list(app.archive.filter(*conditions))
    if not entries:
        flask.abort(404)
    entries.sort(reverse=True)

    return flask.render_template('archive.html', title=title, entries=entries)

@app.route('/<year>/<month>/<day>/<title_slug>/')
def entry_view(title_slug, **kwargs):
    conditions = (date_condition(attribute, int(kwargs[attribute]))
                  for attribute in ['year', 'month', 'day'])
    entries = app.archive.filter(*conditions,
                                 lambda entry: entry.title_slug == title_slug)
    try:
        entry = next(entries)
    except StopIteration:
        flask.abort(404)
    return flask.render_template('entry.html', title=entry.title, entry=entry)

@app.route('/about/')
def about_view():
    return flask.render_template('about.html', title='About')

@app.route('/robots.txt')
def robots_txt_view():
    return flask.send_from_directory(app.static_folder, 'robots.txt',
                                     mimetype='text/plain')

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
def upload():
    cwd = os.getcwd()
    try:
        os.chdir(app.config['FREEZER_DESTINATION'])
        subprocess.run(['git', 'add', '*'])
        subprocess.run(['git', 'commit', '-a', '-m',
                        'automated commit at {:%c}'.format(datetime.now())])
        subprocess.run(['git', 'push'])
    finally:
        os.chdir(cwd)

@main.command()
@click.option('--freeze', is_flag=True)
@click.option('--host')
@click.option('--port', type=int, default=9001, show_default=True)
@click.option('--debug', is_flag=True)
def run(freeze, **kwargs):
    (freezer if freeze else app).run(**kwargs)
