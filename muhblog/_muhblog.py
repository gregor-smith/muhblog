import logging
import pathlib
import datetime
import collections
import configparser

import click
import flask
import slugify
import markdown
import flask_sqlalchemy

DATE_FORMAT = '%Y-%m-%d %H:%M'
CONFIG_DIRECTORY = pathlib.Path(click.get_app_dir('muhblog'))
DATABASE_PATH = CONFIG_DIRECTORY / 'muhblog.db'
MAX_TITLE_LENGTH = 100

app = flask.Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite' + DATABASE_PATH.as_uri()[4:]

db = flask_sqlalchemy.SQLAlchemy(app)

class Entry(db.Model):
    path = db.Column(db.Text, unique=True, primary_key=True)
    title = db.Column(db.String(MAX_TITLE_LENGTH), unique=True)
    markdown_text = db.Column(db.Text, unique=True)
    date_written = db.Column(db.DateTime, unique=True)
    date_modified = db.Column(db.DateTime)
    title_slug = db.Column(db.String(MAX_TITLE_LENGTH))

    def __init__(self, path, title, title_slug,
                 markdown_text, date_written, date_modified):
        self.path = path
        self.title = title
        self.title_slug = title_slug
        self.markdown_text = markdown_text
        self.date_written = date_written
        self.date_modified = date_modified

    @classmethod
    def from_ini_path(cls, path):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(str(path), encoding='utf-8')

        entry = parser['entry']
        title = entry['title']

        return cls(path=str(path),
                   title=title,
                   title_slug=slugify.slugify(title, max_length=MAX_TITLE_LENGTH),
                   markdown_text=entry['text'],
                   date_written=datetime.datetime.strptime(entry['date'], DATE_FORMAT),
                   date_modified=datetime.datetime.fromtimestamp(path.stat().st_mtime))

    def update_from_other(self, other):
        self.path = other.path
        self.title = other.title
        self.title_slug = other.title_slug
        self.markdown_text = other.markdown_text
        self.date_written = other.date_written
        self.date_modified = other.date_modified

    def html_text(self):
        return flask.Markup(markdown.markdown(self.markdown_text))

    def __repr__(self):
        return '{}(path={!r})'.format(type(self).__name__, self.path)

def date_conditions(**kwargs):
    for attribute in {'year', 'month', 'day'}:
        if attribute in kwargs:
            yield db.extract(attribute, Entry.date_written) == kwargs[attribute]

@app.route('/archive')
@app.route('/<int:year>')
@app.route('/<int:year>/<int:month>')
@app.route('/<int:year>/<int:month>/<int:day>')
def archive(**kwargs):
    # I tried using an order_by query to sort the entries and then iterating over them in the
    # template, but the template got so complicated that I just gave up and stuck with these
    # ugly dicts
    entries = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: collections.defaultdict(list)
        )
    )
    conditions = list(date_conditions(**kwargs))
    for entry in Entry.query.filter(*conditions) if conditions else Entry.query:
        month = '{:%m}'.format(entry.date_written)
        day = '{:%d}'.format(entry.date_written)
        entries[str(entry.date_written.year)][month][day].append(entry)
    if not entries:
        flask.abort(404)
    return flask.render_template('archive.html', entries=entries)

@app.route('/<int:year>/<int:month>/<int:day>/<title_slug>')
def entry(title_slug, **kwargs):
    entry = Entry.query.filter(*date_conditions(**kwargs), Entry.title_slug == title_slug).first_or_404()
    return flask.render_template('entry.html', title=entry.title, entry=entry)

def render_error_template(error, image):
    return flask.render_template('error.html', title='{} {}'.format(error.code, error.name),
                                 image=image), error.code

@app.errorhandler(404)
def four_oh_four(error):
    return render_error_template(error, image='/static/404.png')
@app.errorhandler(500)
def five_hunner(error):
    return render_error_template(error, image='/static/500.jpg')
@app.errorhandler(403)
def four_oh_three(error):
    return render_error_template(error, image='/static/403.jpg')

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
        if not pathlib.Path(entry.path).exists():
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
