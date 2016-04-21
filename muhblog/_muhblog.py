import os
import logging
import pathlib
import datetime
import collections
import configparser

import click
import flask
import markdown
import flask_sqlalchemy

DATE_FORMAT = '%Y-%m-%d %H:%M'
CONFIG_DIRECTORY = pathlib.Path(click.get_app_dir('muhblog'))
DATABASE_PATH = CONFIG_DIRECTORY / 'muhblog.db'

app = flask.Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite' + DATABASE_PATH.as_uri()[4:]

db = flask_sqlalchemy.SQLAlchemy(app)

class Entry(db.Model):
    path = db.Column(db.Text, unique=True, primary_key=True)
    title = db.Column(db.String(100), unique=True)
    markdown_text = db.Column(db.Text, unique=True)
    date_written = db.Column(db.DateTime, unique=True)
    date_modified = db.Column(db.DateTime)

    def __init__(self, path, title, markdown_text, date_written, date_modified):
        self.path = path
        self.title = title
        self.markdown_text = markdown_text
        self.date_written = date_written
        self.date_modified = date_modified

    @classmethod
    def from_ini_path(cls, path):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(str(path), encoding='utf-8')
        entry = parser['entry']

        return cls(path=str(path),
                   title=entry['title'],
                   markdown_text=entry['text'],
                   date_written=datetime.datetime.strptime(entry['date'], DATE_FORMAT),
                   date_modified=datetime.datetime.fromtimestamp(path.stat().st_mtime))

    def update_from_other(self, other):
        self.path = other.path
        self.title = other.title
        self.markdown_text = other.markdown_text
        self.date_written = other.date_written
        self.date_modified = other.date_modified

    def html_text(self):
        return markdown.markdown(self.markdown_text)

    def __repr__(self):
        return '{}(path={!r})'.format(type(self).__name__, self.path)

@app.route('/archive')
@app.route('/<year>')
@app.route('/<year>/<month>')
@app.route('/<year>/<month>/<day>')
def archive(**kwargs):
    entries = collections.defaultdict(lambda: collections.defaultdict(list))

    conditions = [db.extract(attribute, Entry.date_written) == kwargs[attribute]
                  for attribute in {'year', 'month', 'day'} if attribute in kwargs]
    for entry in Entry.query.filter(*conditions) if conditions else Entry.query:
        month = '{:0>2}'.format(entry.date_written.month)
        entries[str(entry.date_written.year)][month].append(entry)

    return flask.render_template('archive.html', entries_dict=entries)

def reload_database(archive_path):
    db.create_all()

    for ini_path in pathlib.Path(archive_path).glob('*.ini'):
        new_entry = Entry.from_ini_path(ini_path)
        existing_entry = Entry.query.get(str(ini_path))
        if existing_entry is None:
            logging.debug('no entry found for path, adding new: %s', ini_path)
            db.session.add(new_entry)
        elif new_entry.date_modified > existing_entry.date_modified:
            logging.debug('entry for path has been modified, updating: %s', ini_path)
            existing_entry.update_from_other(new_entry)
        else:
            logging.debug('entry found for path, has not been modified: %s', ini_path)

    for entry in Entry.query:
        if not os.path.exists(entry.path):
            logging.debug('removing entry with nonexistent path from database: %s', entry.path)
            db.session.delete(entry)

    db.session.commit()

@click.command()
@click.option('--host')
@click.option('--port', type=int, default=9001, show_default=True)
@click.option('--debug', is_flag=True, show_default=True)
@click.option('--archive', envvar='BLOG_ARCHIVE_PATH',
              type=click.Path(file_okay=False, writable=True))
def main(host, port, debug, archive):
    if archive is None:
        raise click.BadParameter("either '--archive' must be provided "
                                 "or the 'BLOG_ARCHIVE_PATH' environment variable must be set")

    logging.basicConfig(format='[%(asctime)s %(levelname)s] %(message)s',
                        level=logging.DEBUG if debug else logging.INFO)

    CONFIG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    reload_database(archive)

    app.run(host=host, port=port, debug=debug)
