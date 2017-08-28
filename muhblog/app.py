import os
import shutil
import functools
import subprocess
from pathlib import Path

import click
import flask
from flask_frozen import Freezer

from .views import blueprint
from .models import Entry, AboutPage, TagDefinition, TagMapping, Upload
from .database import db

WINDOWS = os.name == 'nt'
CONFIG_DIRECTORY = click.get_app_dir('muhblog')
CONFIG_FILE_PATH = str(Path(CONFIG_DIRECTORY, 'config.json'))
DEFAULT_CONFIG = {
    'BLOG_NAME': 'muhblog',
    'BLOG_DATABASE_PATH': str(Path(CONFIG_DIRECTORY, 'muhblog.sqlite')),
    'BLOG_ENTRIES_DIRECTORY': str(Path(CONFIG_DIRECTORY, 'entries')),
    'BLOG_UPLOADS_DIRECTORY': str(Path(CONFIG_DIRECTORY, 'uploads')),
    'BLOG_ABOUT_PATH': None,
    'BLOG_FAVICON_PATH': None,
    'BLOG_STYLESHEET_PATH': None,
    'BLOG_ROBOTS_TXT_PATH': None,
    'BLOG_ENTRIES_PER_PAGE': 10,
    'BLOG_SNUB_LENGTH_CHARACTERS': 300,
    'BLOG_SLUG_LENGTH_CHARACTERS': 100,
    'BLOG_PLAYER_SUFFIXES': ['.mp4', '.webm', '.ogg', '.mp3', '.m4a', '.flac'],
    'BLOG_VIDEO_SUFFIXES': ['.mp4', '.webm'],
    'BLOG_DATABASE_CACHE_SIZE': 10000,
    'FREEZER_DESTINATION': str(Path(CONFIG_DIRECTORY, 'freeze')),
    'FREEZER_DESTINATION_IGNORE': ['.git*']
}


def create():
    app = flask.Flask('muhblog')
    app.jinja_env.trim_blocks = app.jinja_env.lstrip_blocks = True
    app.jinja_env.globals['config'] = app.config
    app.jinja_env.filters['format_datetime'] = functools.partial(
        str.format, '{:%d/%m/%Y %H:%M}'
    )
    app.jinja_env.filters['format_datetime_iso'] = functools.partial(
        str.format, '{:%Y-%m-%d %H:%M:%S}'
    )

    app.register_blueprint(blueprint)

    app.config.from_mapping(DEFAULT_CONFIG)
    app.config.from_json(
        os.environ.get('BLOG_CONFIG_FILE_PATH', CONFIG_FILE_PATH),
        silent=True
    )

    db.init_app(app)

    @app.cli.command(name='compile-ts')
    def compile_ts():
        subprocess.run(['tsc.cmd' if WINDOWS else 'tsc',
                        '-p', 'muhblog/typescript'])

    @app.cli.command(name='create-db')
    @db.atomic()
    def create_db():
        db.create_tables(Entry, AboutPage, TagDefinition, TagMapping, Upload)

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

        uploads_directory = Path(app.config['BLOG_UPLOADS_DIRECTORY'])
        print('adding uploads')
        count = 0
        for path in uploads_directory.iterdir():
            if path.is_dir():
                continue
            print(path)
            Upload.create(path)
            count += 1
        print(f'added {count} uploads')

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

    @app.cli.command()
    @click.argument('path', type=click.Path(exists=True, dir_okay=False))
    @click.option('--overwrite', is_flag=True)
    @click.option('--rename', is_flag=True)
    def upload(path, overwrite, rename):
        path = Path(path)
        if rename:
            name = str(round(path.stat().st_mtime * 1000)) + path.suffix
        else:
            name = path.name
        new_path = Path(app.config['BLOG_UPLOADS_DIRECTORY'], name)
        if new_path.exists():
            if not overwrite:
                raise SystemExit(f'path already exists: {new_path}')
            new_path.unlink()

        print(f'symlinking {new_path} to {path}')
        try:
            new_path.symlink_to(path)
            return
        except OSError:
            print(f'lacking permission to symlink, copying instead')
        except NotImplementedError:
            print(f'symlink not implemented on platform, copying instead')
        shutil.copy2(path, new_path)

    return app
