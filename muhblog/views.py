import io
import collections
from pathlib import Path

import scss
import flask

from . import database
from . import app


@app.route('/')
@app.route('/page/<int:page>/')
def front(page=1):
    all_entries = database.connection \
        .execute('SELECT * FROM entries ORDER BY date DESC') \
        .fetchall()
    end = page * app.config['BLOG_ENTRIES_PER_PAGE']
    start = end - app.config['BLOG_ENTRIES_PER_PAGE']
    entries = all_entries[start:end]
    if not entries:
        flask.abort(404)
    return flask.render_template(
        'front.html', title=None, entries=entries, page=page,
        previous_page=None if page == 1 else page - 1,
        next_page=None if entries[-1] == all_entries[-1] else page + 1
    )


@app.route('/archive/')
@app.route('/<year>/')
@app.route('/<year>/<month>/')
@app.route('/<year>/<month>/<day>/')
@app.route('/tag/<slug>/')
def archive(year=None, month=None, day=None, slug=None):
    if slug is not None:
        entries = database.connection \
            .execute('SELECT entries.*, tags.name AS tag_name FROM entries '
                     'JOIN entry_tags ON entries.ROWID = entry_tags.entry_id '
                     'JOIN tags ON entry_tags.tag_id = tags.ROWID '
                     'WHERE tags.slug = ? ', slug) \
            .fetchall()
        title = entries[0]['tag_name']
    elif year is None:
        entries = database.connection \
            .execute('SELECT * FROM entries')
        title = 'archive'
    else:
        if day is not None:
            fmt = '%d/%m/%Y'
            title = f'{day}/{month}/{year}'
        elif month is not None:
            fmt = '%m/%Y'
            title = f'{month}/{year}'
        else:
            fmt = '%Y'
            title = year
        entries = database.connection \
            .execute('SELECT * FROM entries '
                     'WHERE strftime(:format, date) = :desired ',
                     format=fmt, desired=title)

    grouped_entries = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: collections.defaultdict(list)
        )
    )
    for entry in entries:
        date = entry['date']
        grouped_entries[date.year][date.month][date.day].append(entry)

    if not grouped_entries:
        flask.abort(404)

    return flask.render_template('archive.html', title=title,
                                 entries=grouped_entries)


@app.route('/<year>/<month>/<day>/<slug>/')
def entry(slug, **kwargs):
    entry = database.connection \
        .execute('SELECT ROWID, * FROM entries WHERE slug = ?', slug) \
        .fetchone()
    if entry is None:
        flask.abort(404)
    entry_id = entry['ROWID']
    tags = database.connection \
        .execute('SELECT tags.* FROM tags '
                 'JOIN entry_tags ON tags.ROWID = entry_tags.tag_id '
                 'WHERE entry_tags.entry_id = ? '
                 'ORDER BY tags.name COLLATE NOCASE', entry_id)
    scripts = database.connection \
        .execute('SELECT scripts.* FROM scripts '
                 'JOIN entry_scripts ON scripts.ROWID = entry_scripts.script_id '
                 'WHERE entry_scripts.entry_id = ?', entry_id)
    return flask.render_template('entry.html', tags=tags,
                                 scripts=scripts, **entry)


@app.route('/about/')
def about():
    about = database.connection \
        .execute('SELECT * from about') \
        .fetchone()
    return flask.render_template('about.html', title='about', **about)


@app.route('/stylesheet.css')
def stylesheet():
    path = Path(app.static_folder, 'stylesheet.scss')
    css = scss.compiler.compile_file(path)
    file = io.BytesIO(bytes(css, encoding='utf-8'))
    return flask.send_file(file, mimetype='text/css')


@app.route('/robots.txt')
def robots_txt():
    return flask.send_from_directory(app.config['BLOG_USER_STATIC_DIR'],
                                     'robots.txt', mimetype='text/plain')


@app.route('/favicon.png')
def favicon():
    return flask.send_from_directory(app.config['BLOG_USER_STATIC_DIR'],
                                     'favicon.png', mimetype='image/png')


@app.route('/uploads/')
@app.route('/uploads/<path:filename>')
def uploads(filename=None):
    uploads_directory = app.config['BLOG_USER_UPLOADS_DIR']
    if filename is None:
        files = database.connection \
            .execute('SELECT * FROM uploads ORDER BY uploads.date DESC')
        return flask.render_template(
            'uploads.html', files=files, title='uploads',
            scripts=[flask.url_for('static', filename='jquery.js'),
                     flask.url_for('static', filename='tablesorter.js'),
                     flask.url_for('static', filename='sort.js')]
        )
    return flask.send_from_directory(uploads_directory, filename)


@app.route('/player/<path:filename>/')
def player(filename):
    path = Path(app.config['BLOG_USER_UPLOADS_DIR'], filename)
    return flask.render_template(
        'player.html', filename=filename, title=filename,
        is_video=path.suffix in app.config['BLOG_VIDEO_SUFFIXES'],
    )
