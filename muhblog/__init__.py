import os
import re
import functools
from pathlib import Path

import click
import flask
import flask_frozen

WINDOWS = os.name == 'nt'
APP_DIR = Path(click.get_app_dir('muhblog'))
CONFIG_FILE = APP_DIR.joinpath('config.json')


def snubify(text):
    match = re.search(r'<p>((?:(?!<\/p>).){{1,{}}}\.)'
                          .format(app.config['BLOG_SNUB_LENGTH']),
                      text, re.DOTALL)
    snub = match.group(1)
    return flask.Markup(f'<p>{snub}</p>')


app = flask.Flask(__name__)
app.config['BLOG_TITLE'] = 'muhblog'
app.config['BLOG_USER_ARCHIVE_DIR'] = os.fspath(APP_DIR.joinpath('archive'))
app.config['BLOG_USER_UPLOADS_DIR'] = os.fspath(APP_DIR.joinpath('uploads'))
app.config['BLOG_USER_STATIC_DIR'] = os.fspath(APP_DIR.joinpath('static'))
app.config['BLOG_ENTRIES_PER_PAGE'] = 10
app.config['BLOG_SNUB_LENGTH'] = 300
app.config['BLOG_SLUG_LENGTH'] = 100
app.config['BLOG_VIDEO_SUFFIXES'] = {'.mp4', '.webm'}
app.config['BLOG_PLAYER_SUFFIXES'] = {'.ogg', '.mp3', '.m4a', '.flac',
                                      *app.config['BLOG_VIDEO_SUFFIXES']}
app.config['FREEZER_DESTINATION'] = os.fspath(APP_DIR.joinpath('freeze'))
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*']

app.jinja_env.filters['snubify'] = snubify
app.jinja_env.filters['pad_date_int'] = functools.partial(str.format, '{:0>2}')
app.jinja_env.filters['format_datetime'] = functools.partial(
    str.format, '{:%d/%m/%Y %H:%M}'
)
app.jinja_env.filters['format_datetime_iso'] = functools.partial(
    str.format, '{:%Y-%m-%d %H:%M}'
)

app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True
app.jinja_env.globals['app_config'] = app.config

freezer = flask_frozen.Freezer(app)

# must be imported to add views to app as it's not imported anywhere else
from . import views
from .cli import main
