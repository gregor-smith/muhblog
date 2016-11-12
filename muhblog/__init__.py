import os
from pathlib import Path

import click
import flask
import flask_frozen

WINDOWS = os.name == 'nt'
APP_DIR = Path(click.get_app_dir('muhblog'))
CONFIG_FILE = APP_DIR.joinpath('config.json')
VIDEO_SUFFIXES = {'.mp4', '.webm'}
PLAYER_SUFFIXES = {'.ogg', '.mp3', '.m4a', *VIDEO_SUFFIXES}
ENTRIES_PER_PAGE = 10
SNUB_LENGTH = 300

app = flask.Flask(__name__)
app.config['BLOG_TITLE'] = 'muhblog'
app.config['BLOG_APP_DIR'] = os.fspath(APP_DIR)
app.config['BLOG_USER_ARCHIVE_DIR'] = os.fspath(APP_DIR.joinpath('archive'))
app.config['BLOG_USER_UPLOADS_DIR'] = os.fspath(APP_DIR.joinpath('uploads'))
app.config['BLOG_USER_STATIC_DIR'] = os.fspath(APP_DIR.joinpath('static'))
app.config['FREEZER_DESTINATION'] = os.fspath(APP_DIR.joinpath('freeze'))
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*']

app.jinja_env.filters['pad_date'] = lambda date: '{:0>2}'.format(date)
app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True
app.jinja_env.globals['app_config'] = app.config

freezer = flask_frozen.Freezer(app)

# must be imported to add views to app as it's not imported anywhere else
from . import views
from .cli import main
