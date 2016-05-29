import os
import ctypes
import shutil
import functools
import subprocess
from pathlib import Path
from datetime import datetime

import click
import flask
import markdown
import flask.ext.frozen
import markdown.extensions.meta
from slugify import slugify

WINDOWS = os.name == 'nt'

APP_DIRECTORY = Path(click.get_app_dir('muhblog'))
FREEZE_DIRECTORY = APP_DIRECTORY.joinpath('freeze')
UPLOADS_DIRECTORY = APP_DIRECTORY.joinpath('uploads')

app = flask.Flask(__name__)
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*']
app.config['FREEZER_DESTINATION'] = str(FREEZE_DIRECTORY)
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

def format_datetime(dt=None):
    return '{:%d/%m/%Y %T}'.format(dt or datetime.now())
app.jinja_env.filters['format_datetime'] = format_datetime

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

@app.route('/uploads/')
@app.route('/uploads/<path:filename>')
def uploads_view(filename=None):
    if filename is not None:
        return flask.send_from_directory(str(UPLOADS_DIRECTORY), filename)
    return flask.render_template('uploads.html', title='Uploads',
                                 directory=UPLOADS_DIRECTORY,
                                 datetime=datetime)

@click.group()
@click.option('--archive-path', envvar='BLOG_ARCHIVE_PATH',
              type=click.Path(file_okay=False, writable=True))
def main(archive_path):
    if archive_path is None:
        raise click.BadParameter("either '--archive-path' must be provided "
                                 "or the 'BLOG_ARCHIVE_PATH' environment "
                                 'variable must be set')
    app.archive = Archive(Path(archive_path))

@main.command()
def freeze():
    freezer.freeze()

def push_frozen_git(silent=False):
    if silent:
        kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
    else:
        kwargs = {}
    run_subprocess = functools.partial(subprocess.run, **kwargs)

    cwd = os.getcwd()
    try:
        os.chdir(str(FREEZE_DIRECTORY))
        run_subprocess(['git', 'add', '*'])
        run_subprocess(['git', 'commit', '-a', '-m',
                        'automated commit at {}'.format(format_datetime())])
        run_subprocess(['git', 'push'])
    finally:
        os.chdir(cwd)

@main.command()
def push():
    push_frozen_git()

@main.command()
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
@click.option('--url', envvar='BLOG_URL')
@click.option('--push', is_flag=True)
@click.option('--overwrite', is_flag=True)
@click.option('--rename', is_flag=True)
@click.option('--clipboard', is_flag=True)
def upload(path, url, push, overwrite, rename, clipboard):
    path = Path(path).absolute()
    if rename:
        name = str(datetime.now().timestamp()) + path.suffix
    else:
        name = path.name
    destination = UPLOADS_DIRECTORY.joinpath(name)
    if destination.exists():
        if overwrite:
            destination.unlink()
        else:
            raise SystemExit('path already exists: {}'.format(destination))
    if WINDOWS:
        if ctypes.windll.shell32.IsUserAnAdmin():
            destination.symlink_to(path)
            print('symlink created:', destination)
        elif path.drive == destination.drive:
            subprocess.run(['mklink', '/H', str(destination), str(path)],
                           shell=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
            print('hardlink created:', destination)
        else:
            shutil.copy2(str(path), str(destination))
            print('copy created:', destination)
    else:
        destination.symlink_to(path)
        print('symlink created:', destination)

    if push:
        push_frozen_git(silent=True)
    if url is not None:
        with app.test_request_context():
            file_url = url + flask.url_for('uploads_view', filename=name)
        print(file_url)
        if clipboard:
            subprocess.run(['clip' if WINDOWS else 'xclip'],
                           input=file_url, universal_newlines=True)

@main.command()
@click.option('--freeze', is_flag=True)
@click.option('--host')
@click.option('--port', type=int, default=9001, show_default=True)
@click.option('--debug', is_flag=True)
def run(freeze, **kwargs):
    (freezer if freeze else app).run(**kwargs)
