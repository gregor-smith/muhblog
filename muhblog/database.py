import sqlite3
from pathlib import Path
from datetime import datetime

import flask
import markdown
from slugify import slugify
from markdown.extensions.meta import MetaExtension

from . import app, PLAYER_SUFFIXES

def convert_markup(bytes):
    return flask.Markup(str(bytes, encoding='utf-8'))
sqlite3.register_converter('MARKUP', convert_markup)

class Cursor(sqlite3.Cursor):
    def execute(self, sql, *args, **kwargs):
        return super().execute(sql, kwargs or tuple(args))

class Connection(sqlite3.Connection):
    def cursor(self, factory=Cursor):
        return super().cursor(factory=factory)

    def execute(self, *args, **kwargs):
        cursor = self.cursor()
        cursor.execute(*args, **kwargs)
        return cursor

connection = sqlite3.connect(':memory:', factory=Connection,
                             detect_types=sqlite3.PARSE_DECLTYPES)
connection.row_factory = sqlite3.Row

class SpoilerTagPattern(markdown.inlinepatterns.Pattern):
    regex_pattern = r'\[spoiler\](?P<text>.+?)\[/spoiler\]'

    def __init__(self, markdown_instance=None):
        super().__init__(self.regex_pattern, markdown_instance)

    def handleMatch(self, match):
        element = markdown.util.etree.Element('span')
        element.set('class', 'spoiler')
        element.text = markdown.util.AtomicString(match.group('text'))
        return element

class SpoilerTagExtension(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        md.inlinePatterns[type(self).__name__] = SpoilerTagPattern(md)

class Entry:
    def __init__(self, path):
        self.path = path
        parser = markdown.Markdown(extensions=[MetaExtension(),
                                               SpoilerTagExtension()])

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

class AboutPage(Entry):
    def __init__(self, path):
        self.path = path
        self.text = markdown.markdown(path.read_text(encoding='utf-8'),
                                      extensions=[SpoilerTagExtension()])

    def as_sql_args(self):
        return {'text': self.text}

class Upload:
    def __init__(self, path):
        self.path = path
        stat = path.stat()

        self.filename = path.name
        self.filesize = stat.st_size
        self.date_modified = datetime.fromtimestamp(stat.st_mtime)
        self.view = 'player' if path.suffix in PLAYER_SUFFIXES else 'uploads'

    def as_sql_args(self):
        return {'filename': self.filename, 'filesize': self.filesize,
                'date_modified': self.date_modified, 'view': self.view}

def create_and_populate():
    cursor = connection.cursor()
    with connection:
        create_tables(cursor)
        add_entries(cursor)
        add_uploads(cursor)
        add_about(cursor)

def create_tables(cursor):
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
    cursor.execute('CREATE TABLE about (text MARKUP)')

def add_entries(cursor):
    for path in Path(app.config['BLOG_USER_ARCHIVE_DIR']).glob('*.md'):
        if not path.is_file():
            continue
        entry = Entry(path)
        cursor.execute('''INSERT INTO entries
                          VALUES (:slug, :title,
                                  :text, :date_written)''',
                       **entry.as_sql_args())
        entry_id = cursor.lastrowid
        for slug, tag in entry.tags.items():
            cursor.execute('INSERT OR IGNORE INTO tags '
                           'VALUES (?, ?)', slug, tag)
            cursor.execute('INSERT INTO entry_tags VALUES (?, ?)',
                           entry_id, cursor.lastrowid)
        for script in entry.scripts:
            cursor.execute('INSERT OR IGNORE INTO scripts VALUES (?)', script)
            cursor.execute('INSERT INTO entry_scripts VALUES (?, ?)',
                           entry_id, cursor.lastrowid)

def add_uploads(cursor):
    for path in Path(app.config['BLOG_USER_UPLOADS_DIR']).iterdir():
        if not path.is_file():
            continue
        upload = Upload(path)
        cursor.execute('''INSERT INTO uploads
                          VALUES (:filename, :filesize,
                                  :date_modified, :view)''',
                       **upload.as_sql_args())

def add_about(cursor):
    about_path = Path(app.config['BLOG_USER_STATIC_DIR'], 'about.md')
    if about_path.exists():
        about = AboutPage(about_path)
        cursor.execute('INSERT INTO about VALUES (:text)',
                       **about.as_sql_args())
    else:
        text = markdown.markdown('No `about.md` could be found '
                                 'in `BLOG_USER_STATIC_DIR`')
        cursor.execute('INSERT INTO about VALUES (?)', text)
