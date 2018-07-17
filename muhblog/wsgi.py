import os
from pathlib import Path

import click
import flask
from flask_frozen import Freezer

from . import controllers, filters
from .models import Entry, AboutPage, TagDefinition, TagMapping
from .database import db

WINDOWS = os.name == 'nt'
CONFIG_DIRECTORY = click.get_app_dir('muhblog')
CONFIG_FILE_PATH = str(Path(CONFIG_DIRECTORY, 'config.json'))
DEFAULT_CONFIG = {
    'BLOG_NAME': 'muhblog',
    'BLOG_DATABASE_PATH': str(Path(CONFIG_DIRECTORY, 'muhblog.sqlite')),
    'BLOG_ENTRIES_DIRECTORY': str(Path(CONFIG_DIRECTORY, 'entries')),
    'BLOG_ABOUT_PATH': None,
    'BLOG_FAVICON_PATH': None,
    'BLOG_STYLESHEET_PATH': None,
    'BLOG_ROBOTS_TXT_PATH': None,
    'BLOG_ENTRIES_PER_PAGE': 10,
    'BLOG_SNUB_LENGTH_CHARACTERS': 300,
    'BLOG_SLUG_LENGTH_CHARACTERS': 100,
    'FREEZER_DESTINATION': str(Path(CONFIG_DIRECTORY, 'freeze')),
    'FREEZER_DESTINATION_IGNORE': ['.git*']
}


def create():
    app = flask.Flask('muhblog')
    app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True
    app.jinja_env.globals['config'] = app.config

    app.register_blueprint(controllers.blueprint)
    app.register_blueprint(filters.blueprint)

    app.config.from_mapping(DEFAULT_CONFIG)
    app.config.from_json(
        os.environ.get('BLOG_CONFIG_FILE_PATH', CONFIG_FILE_PATH),
        silent=True
    )

    db.init_app(app)

    @app.cli.command(name='create-db')
    @db.atomic()
    def create_db():
        db.create_tables(Entry, AboutPage, TagDefinition, TagMapping)

        archive_directory = Path(app.config['BLOG_ENTRIES_DIRECTORY'])
        print('adding entries')
        count = 0
        for path in archive_directory.glob('*.md'):
            if path.is_dir():
                continue
            print(path)
            Entry.create(path)
            count += 1
        print(f'added {count} entries')

        if app.config['BLOG_ABOUT_PATH'] is None:
            AboutPage.create_default()
            print('no about page found, adding default')
        else:
            AboutPage.create(app.config['BLOG_ABOUT_PATH'])

    @app.cli.command()
    def freeze():
        freezer = Freezer(app)
        print(f'freezing to {app.config["FREEZER_DESTINATION"]}')
        freezer.freeze()

    @app.cli.command('run-frozen')
    def run_frozen():
        freezer = Freezer(app)
        freezer.run()

    return app
