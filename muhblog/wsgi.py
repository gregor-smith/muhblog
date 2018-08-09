from pathlib import Path

from flask import Flask
from flask_frozen import Freezer

from . import controllers, filters
from .models import Entry, Tag, EntryTag, AboutPage
from .database import database

DEFAULT_CONFIG = {
    'BLOG_NAME': 'muhblog',
    'BLOG_ENTRIES_DIRECTORY': str(Path.cwd().joinpath('entries')),
    'BLOG_ABOUT_PATH': str(Path.cwd().joinpath('about.md')),
    'FREEZER_DESTINATION': str(Path.cwd().joinpath('freeze')),
    'FREEZER_DESTINATION_IGNORE': ['.git*']
}
CONFIG_FILE_PATH = str(Path.cwd().joinpath('config.json'))


@database.atomic()
def initialise_database(app: Flask) -> None:
    entries_directory = Path(app.config['BLOG_ENTRIES_DIRECTORY'])
    if not entries_directory.exists():
        app.logger.error(
            'BLOG_ENTRIES_DIRECTORY "%s" does not exist',
            entries_directory
        )
        return
    if not entries_directory.is_dir():
        app.logger.error(
            'BLOG_ENTRIES_DIRECTORY "%s" is not a directory',
            entries_directory
        )
        return

    about_path = Path(app.config['BLOG_ABOUT_PATH'])
    if not about_path.exists():
        app.logger.error('BLOG_ABOUT_PATH "%s" does not exist', about_path)
        return
    if not about_path.is_file():
        app.logger.error('BLOG_ABOUT_PATH "%s" is not a file', about_path)
        return

    app.logger.debug('Creating tables')
    database.create_tables([Entry, Tag, EntryTag, AboutPage])

    app.logger.info('Parsing entries')
    entry_paths = [path for path in entries_directory.glob('*.md') if path.is_file()]
    for index, path in enumerate(entry_paths, start=1):
        app.logger.info('Adding %s/%s "%s"', index, len(entry_paths), path)
        text = path.read_text(encoding='utf-8')
        Entry.create(text=text)

    app.logger.info('Adding about page "%s"', about_path)
    about_text = about_path.read_text(encoding='utf-8')
    AboutPage.create(text=about_text)


def create() -> Flask:
    app = Flask('muhblog')

    app.register_blueprint(controllers.blueprint)
    app.register_blueprint(filters.blueprint)

    app.config.from_mapping(DEFAULT_CONFIG)
    app.config.from_json(CONFIG_FILE_PATH)
    app.logger.setLevel('DEBUG' if app.debug else 'INFO')

    initialise_database(app)

    @app.cli.command()
    def freeze() -> None:
        freezer = Freezer(app)
        app.logger.info('Freezing to %s', app.config['FREEZER_DESTINATION'])
        freezer.freeze()

    return app
