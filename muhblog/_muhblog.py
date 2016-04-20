import os
import logging
import pathlib
import datetime
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
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), unique=True)
    date_written = db.Column(db.DateTime, unique=True)
    date_modified = db.Column(db.DateTime)
    markdown_text = db.Column(db.Text, unique=True)
    path = db.Column(db.Text, unique=True)

    def __init__(self, **kwargs):
        self.update_from_arguments(**kwargs)

    def update_from_arguments(self, title, markdown_text, date_written,
                              path=None, date_modified=None):
        self.title = title
        self.markdown_text = markdown_text
        self.date_written = date_written
        if path is not None:
            self.path = path
        if date_modified is not None:
            self.date_modified = date_modified

    @staticmethod
    def arguments_from_ini_path(path):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(str(path), encoding='utf-8')
        entry = parser['entry']

        return {'title': entry['title'], 'markdown_text': entry['text'], 'path': str(path),
                'date_written': datetime.datetime.strptime(entry['date'], DATE_FORMAT),
                'date_modified': datetime.datetime.fromtimestamp(path.stat().st_mtime)}

    def html_text(self):
        return markdown.markdown(self.markdown_text)

@app.route('/')
def entry():
    return flask.render_template('entry.html')

def reload_database(archive_path):
    db.create_all()

    for ini_path in pathlib.Path(archive_path).glob('*.ini'):
        arguments = Entry.arguments_from_ini_path(ini_path)
        existing_entry = Entry.query.filter_by(path=str(ini_path)).first()
        if existing_entry is None:
            logging.debug('no entry found for path, adding new: %s', ini_path)
            db.session.add(Entry(**arguments))
        elif arguments['date_modified'] > existing_entry.date_modified:
            logging.debug('entry for path has been modified, updating: %s', ini_path)
            existing_entry.update_from_arguments(**arguments)
        else:
            logging.debug('entry found for path, has not been modified: %s', ini_path)

    for entry in Entry.query.all():
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
