import logging
import pathlib
import datetime
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
    is_hidden = db.Column(db.Boolean)

    def __init__(self, path, title, title_slug, markdown_text,
                 date_written, date_modified, is_hidden):
        self.path = path
        self.title = title
        self.title_slug = title_slug
        self.markdown_text = markdown_text
        self.date_written = date_written
        self.date_modified = date_modified
        self.is_hidden = is_hidden

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
                   date_modified=datetime.datetime.fromtimestamp(path.stat().st_mtime),
                   is_hidden=parser.getboolean('entry', 'is_hidden', fallback=True))

    def update_from_other(self, other):
        self.path = other.path
        self.title = other.title
        self.title_slug = other.title_slug
        self.markdown_text = other.markdown_text
        self.date_written = other.date_written
        self.date_modified = other.date_modified
        self.is_hidden = other.is_hidden

    def html_text(self):
        return flask.Markup(markdown.markdown(self.markdown_text))

    def __repr__(self):
        return '{}(path={!r})'.format(type(self).__name__, self.path)

def date_conditions(**kwargs):
    for attribute in ['year', 'month', 'day']:
        if attribute in kwargs:
            yield db.extract(attribute, Entry.date_written) == kwargs[attribute]

@app.route('/archive')
@app.route('/<int:year>')
@app.route('/<int:year>/<int:month>')
@app.route('/<int:year>/<int:month>/<int:day>')
def archive(**kwargs):
    conditions = list(date_conditions(**kwargs))
    if not app.show_hidden:
        conditions.append(Entry.is_hidden.is_(False))
    query = Entry.query.filter(*conditions).order_by(Entry.date_written.desc())
    return flask.render_template('archive.html', title='Archive', entries=query)

@app.route('/<int:year>/<int:month>/<int:day>/<title_slug>')
def entry(title_slug, **kwargs):
    conditions = [*date_conditions(**kwargs), Entry.title_slug == title_slug]
    if not app.show_hidden:
        conditions.append(Entry.is_hidden.is_(False))
    entry = Entry.query.filter(*conditions).first_or_404()
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
@click.option('--archive', envvar='BLOG_ARCHIVE_PATH',
              type=click.Path(file_okay=False, writable=True))
@click.option('--host')
@click.option('--port', type=int, default=9001, show_default=True)
@click.option('--debug', is_flag=True, show_default=True)
@click.option('--show-hidden', is_flag=True, show_default=True)
def main(archive, host, port, debug, show_hidden):
    if archive is None:
        raise click.BadParameter("either '--archive' must be provided "
                                 "or the 'BLOG_ARCHIVE_PATH' environment variable must be set")

    logging.basicConfig(format='[%(asctime)s %(levelname)s] %(message)s',
                        level=logging.DEBUG if debug else logging.INFO)

    CONFIG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    reload_database(archive)

    app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True
    app.show_hidden = show_hidden
    app.run(host=host, port=port, debug=debug)
