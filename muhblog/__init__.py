import os
import ctypes
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

import click
import flask
import markdown
import flask_frozen
import markdown.extensions.meta
from slugify import slugify

WINDOWS = os.name == 'nt'

APP_DIR = Path(click.get_app_dir('muhblog'))

app = flask.Flask(__name__)
app.config['BLOG_URL'] = None
app.config['BLOG_APP_DIRECTORY'] = str(APP_DIR)
app.config['BLOG_ARCHIVE_DIRECTORY'] = str(APP_DIR.joinpath('archive'))
app.config['BLOG_UPLOADS_DIRECTORY'] = str(APP_DIR.joinpath('uploads'))
app.config['FREEZER_DESTINATION'] = str(APP_DIR.joinpath('freeze'))
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*']
app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True

freezer = flask_frozen.Freezer(app)

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
        self.parser = markdown.Markdown(
            extensions=[markdown.extensions.meta.MetaExtension(),
                        SpoilerTagExtension()]
        )

        self.text = flask.Markup(
            self.parser.convert(self.path.read_text(encoding='utf-8'))
        )
        self.title = self.parser.Meta['title'][0]
        self.title_slug = slugify(self.title, max_length=100)
        self.date_written = datetime.strptime(self.parser.Meta['date'][0],
                                              '%Y-%m-%d %H:%M')
        self.tags = {slugify(tag): tag for tag in self.parser.Meta['tags']}

    def __repr__(self):
        return '{}(path={!r})'.format(type(self).__name__, self.path)

    def __lt__(self, other):
        try:
            return self.date_written < other.date_written
        except (AttributeError, TypeError):
            return NotImplemented

class Archive(dict):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.tags = {}

    __repr__ = Entry.__repr__

    def reload(self):
        archive_directory = Path(self.app.config['BLOG_ARCHIVE_DIRECTORY'])
        for path in archive_directory.glob('*.md'):
            if path.is_file():
                self[path] = entry = Entry(path)
                self.tags.update(entry.tags)

    def filter(self, *conditions):
        for entry in self.values():
            if all(condition(entry) for condition in conditions):
                yield entry

archive = Archive(app)

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
        title = archive.tags[tag_slug]
        conditions.append(lambda entry: tag_slug in entry.tags)
    else:
        title = None

    entries = list(archive.filter(*conditions))
    if not entries:
        flask.abort(404)
    entries.sort(reverse=True)

    return flask.render_template('archive.html', title=title, entries=entries)

@app.route('/<year>/<month>/<day>/<title_slug>/')
def entry_view(title_slug, **kwargs):
    conditions = (date_condition(attribute, int(kwargs[attribute]))
                  for attribute in ['year', 'month', 'day'])
    entries = archive.filter(*conditions,
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

def format_datetime(dt=None):
    return '{:%d/%m/%Y %T}'.format(dt or datetime.now())
app.jinja_env.filters['format_datetime'] = format_datetime

@app.route('/uploads/')
@app.route('/uploads/<path:filename>')
def uploads_view(filename=None):
    uploads_directory = app.config['BLOG_UPLOADS_DIRECTORY']
    if filename is None:
        return flask.render_template('uploads.html', title='Uploads',
                                     timestamp_parser=datetime.fromtimestamp,
                                     directory=Path(uploads_directory))
    return flask.send_from_directory(str(uploads_directory), filename)
    flask.send_file()

@click.group()
@click.option('--config-path', envvar='BLOG_CONFIG_PATH',
              default=str(APP_DIR.joinpath('config.json')),
              type=click.Path(dir_okay=False, exists=True))
def main(config_path):
    app.config.from_json(config_path, silent=True)
    archive.reload()

@main.command()
def freeze():
    freezer.freeze()

def push_frozen_git(message=None):
    cwd = os.getcwd()
    try:
        os.chdir(app.config['FREEZER_DESTINATION'])
        subprocess.run(['git', 'add', '*'])
        subprocess.run(['git', 'commit', '-a', '-m', message])
        subprocess.run(['git', 'push'])
    finally:
        os.chdir(cwd)

@main.command()
@click.option('-m', '--message',
              default=lambda: 'push called at {}'.format(datetime.now()))
def push(message):
    push_frozen_git(message)

@main.command()
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
@click.option('--url', default=lambda: app.config['BLOG_URL'])
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
    destination = Path(app.config['BLOG_UPLOADS_DIRECTORY'], name)
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
        freezer.freeze()
        push_frozen_git('uploaded {} at {}'.format(name, datetime.now()))
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
