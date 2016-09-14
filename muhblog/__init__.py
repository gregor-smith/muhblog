import os
import sqlite3
import functools
import subprocess
from pathlib import Path
from datetime import datetime

import click
import flask
import symlink
import markdown
import flask_frozen
import markdown.extensions.meta
from slugify import slugify

WINDOWS = os.name == 'nt'
APP_DIR = Path(click.get_app_dir('muhblog'))
CONFIG_FILE = APP_DIR.joinpath('config.json')
VIDEO_SUFFIXES = {'.mp4', '.webm'}
PLAYER_SUFFIXES = {'.ogg', '.mp3', '.m4a', *VIDEO_SUFFIXES}

app = flask.Flask(__name__)
app.config['BLOG_URL'] = None
app.config['BLOG_APP_DIRECTORY'] = str(APP_DIR)
app.config['BLOG_ARCHIVE_DIRECTORY'] = str(APP_DIR.joinpath('archive'))
app.config['BLOG_UPLOADS_DIRECTORY'] = str(APP_DIR.joinpath('uploads'))
app.config['FREEZER_DESTINATION'] = str(APP_DIR.joinpath('freeze'))
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*']
app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True

def format_datetime(dt=None):
    return '{:%d/%m/%Y %T}'.format(dt or datetime.now())
app.jinja_env.filters['format_datetime'] = format_datetime

def convert_markup(bytes):
    return flask.Markup(str(bytes, encoding='utf-8'))
sqlite3.register_converter('MARKUP', convert_markup)

database = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)
database.row_factory = sqlite3.Row

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

        parser = markdown.Markdown(
                extensions=[markdown.extensions.meta.MetaExtension(),
                            SpoilerTagExtension()]
        )

        self.text = parser.convert(path.read_text(encoding='utf-8'))
        self.title = parser.Meta['title'][0]
        self.slug = slugify(self.title, max_length=100)
        self.date_written = datetime.strptime(parser.Meta['date'][0],
                                              '%Y-%m-%d %H:%M')

        self.tags = {slugify(tag): tag for tag in parser.Meta['tags']}
        self.scripts = parser.Meta.get('scripts', [])

    def as_sql_args(self):
        return {'text': self.text, 'title': self.title,
                'slug': self.slug, 'date_written': self.date_written}

class Upload:
    def __init__(self, path):
        self.path = path
        stat = path.stat()

        self.filename = path.name
        self.filesize = stat.st_size
        self.date_modified = datetime.fromtimestamp(stat.st_mtime)
        self.view = ('player_view' if path.suffix
                     in PLAYER_SUFFIXES else 'uploads_view')

    def as_sql_args(self):
        return {'filename': self.filename, 'filesize': self.filesize,
                'date_modified': self.date_modified, 'view': self.view}

def create_database():
    cursor = database.cursor()

    with database:
        cursor.execute('''CREATE TABLE entries (slug TEXT,
                                                title TEXT, text MARKUP,
                                                date_written TIMESTAMP)''')
        cursor.execute('CREATE TABLE tags (slug TEXT, name TEXT)')
        cursor.execute('''CREATE TABLE entry_tags (entry_id INT,
                                                   tag_id INT)''')
        cursor.execute('CREATE TABLE scripts (url TEXT)')
        cursor.execute('''CREATE TABLE entry_scripts (entry_id INT,
                                                      script_id INT)''')
        cursor.execute('''CREATE TABLE uploads (filename TEXT, filesize INT,
                                                date_modified TIMESTAMP,
                                                view TEXT)''')

        for path in Path(app.config['BLOG_ARCHIVE_DIRECTORY']).glob('*.md'):
            if not path.is_file():
                continue
            entry = Entry(path)
            cursor.execute('''INSERT INTO entries
                              VALUES (:slug, :title,
                                      :text, :date_written)''',
                           entry.as_sql_args())
            entry_id = cursor.lastrowid
            for slug, tag in entry.tags.items():
                cursor.execute('INSERT OR IGNORE INTO tags '
                               'VALUES (?, ?)', (slug, tag))
                cursor.execute('INSERT INTO entry_tags VALUES (?, ?)',
                               (entry_id, cursor.lastrowid))
            for script in entry.scripts:
                cursor.execute('INSERT OR IGNORE INTO scripts VALUES (?)',
                               (script,))
                cursor.execute('INSERT INTO entry_scripts VALUES (?, ?)',
                               (entry_id, cursor.lastrowid))

        for path in Path(app.config['BLOG_UPLOADS_DIRECTORY']).iterdir():
            if not path.is_file():
                continue
            upload = Upload(path)
            cursor.execute('''INSERT INTO uploads
                              VALUES (:filename, :filesize,
                                      :date_modified, :view)''',
                           upload.as_sql_args())

@app.route('/tag/<tag_slug>/')
def tag_view(tag_slug):
    entries = database.execute(
        'SELECT entries.*, tags.name AS tag_name FROM entries '
        'JOIN entry_tags ON entries.ROWID = entry_tags.entry_id '
        'JOIN tags ON entry_tags.tag_id = tags.ROWID '
        'WHERE tags.slug = ? '
        'ORDER BY entries.date_written DESC',
        (tag_slug,)
    )
    entries = entries.fetchall()
    if not entries:
        flask.abort(404)
    return flask.render_template('archive.html', entries=entries,
                                 title=entries[0]['tag_name'])

@app.route('/')
@app.route('/<year>/')
@app.route('/<year>/<month>/')
@app.route('/<year>/<month>/<day>/')
def archive_view(year=None, month=None, day=None):
    if year is None:
        entries = database.execute('SELECT * FROM entries '
                                   'ORDER BY date_written DESC')
        title = None
    else:
        if day is not None:
            format = '%d/%m/%Y'
            title = '{}/{}/{}'.format(day, month, year)
        elif month is not None:
            format = '%m/%Y'
            title = '{}/{}'.format(month, year)
        else:
            format = '%Y'
            title = year
        entries = database.execute('SELECT * FROM entries '
                                   'WHERE strftime(?, date_written) = ? '
                                   'ORDER BY date_written DESC',
                                   (format, title))

    entries = entries.fetchall()
    if not entries:
        flask.abort(404)
    return flask.render_template('archive.html', title=title, entries=entries)

@app.route('/<year>/<month>/<day>/<slug>/')
def entry_view(slug, **kwargs):
    entry = database.execute('SELECT ROWID, * FROM entries '
                             'WHERE slug = ?', (slug,)) \
        .fetchone()
    if entry is None:
        flask.abort(404)
    entry_id = entry['ROWID']
    tags = database.execute(
        'SELECT tags.* FROM tags '
        'JOIN entry_tags ON tags.ROWID = entry_tags.tag_id '
        'WHERE entry_tags.entry_id = ? '
        'ORDER BY tags.name COLLATE NOCASE',
        (entry_id,)
    )
    scripts = database.execute('SELECT scripts.* FROM scripts '
                               'JOIN entry_scripts '
                               'ON scripts.ROWID = entry_scripts.script_id '
                               'WHERE entry_scripts.entry_id = ?', (entry_id,))
    return flask.render_template('entry.html', tags=tags,
                                 scripts=scripts, **entry)

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
    uploads_directory = app.config['BLOG_UPLOADS_DIRECTORY']
    if filename is None:
        files = database.execute('SELECT * FROM uploads '
                                 'ORDER BY uploads.date_modified DESC')
        return flask.render_template('uploads.html', files=files,
                                     title='Uploads')
    return flask.send_from_directory(uploads_directory, filename)

@app.route('/player/<path:filename>/')
def player_view(filename):
    path = Path(app.config['BLOG_UPLOADS_DIRECTORY'], filename)
    return flask.render_template('player.html', filename=filename,
                                 is_video=path.suffix in VIDEO_SUFFIXES,
                                 title=filename)

@click.group()
@click.option('--config-path', envvar='BLOG_CONFIG_PATH',
              type=click.Path(dir_okay=False, exists=True),
              default=str(CONFIG_FILE))
def main(config_path):
    app.config.from_json(config_path, silent=True)
    create_database()

@main.command()
def freeze():
    freezer.freeze()

def push_frozen_git(message=None):
    run = functools.partial(subprocess.run,
                            cwd=app.config['FREEZER_DESTINATION'])
    run(['git', 'add', '.'])
    run(['git', 'commit', '-am', message])
    run(['git', 'push'])

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

    link_type = symlink.link(destination, path, copy_fallback=True)
    if link_type is symlink.LinkType.symlink:
        print('symlink created:', destination)
    elif link_type is symlink.LinkType.hardlink:
        print('hardlink created:', destination)
    else:
        print('copy created:', destination)

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