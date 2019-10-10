from pathlib import Path

from flask import Flask
from flask_frozen import Freezer

from . import controllers
from .models import Entry, Tag, EntryTag, AboutPage
from .database import database


DEFAULT_CONFIG = {
    'NAME': 'muhblog',
    'ENTRIES_DIRECTORY': str(Path.cwd().joinpath('entries')),
    'ABOUT_PATH': str(Path.cwd().joinpath('about.md')),
    'OUTPUT_DIRECTORY': str(Path.cwd().joinpath('freeze')),
    'OUTPUT_IGNORE': ['.git*']
}
CONFIG_FILE_PATH = str(Path.cwd().joinpath('config.json'))


@database.atomic()
def initialise_database(app: Flask) -> None:
    entries_directory = Path(app.config['ENTRIES_DIRECTORY'])
    if not entries_directory.exists():
        app.logger.error(
            'ENTRIES_DIRECTORY "%s" does not exist',
            entries_directory
        )
        return
    if not entries_directory.is_dir():
        app.logger.error(
            'ENTRIES_DIRECTORY "%s" is not a directory',
            entries_directory
        )
        return

    about_path = Path(app.config['ABOUT_PATH'])
    if not about_path.exists():
        app.logger.error('ABOUT_PATH "%s" does not exist', about_path)
        return
    if not about_path.is_file():
        app.logger.error('ABOUT_PATH "%s" is not a file', about_path)
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

    app.config.from_mapping(DEFAULT_CONFIG)
    app.config.from_json(CONFIG_FILE_PATH)
    app.config['FREEZER_DESTINATION'] = app.config['OUTPUT_DIRECTORY']
    app.config['FREEZER_DESTINATION_IGNORE'] = app.config['OUTPUT_IGNORE']
    app.logger.setLevel('DEBUG' if app.debug else 'INFO')

    initialise_database(app)

    @app.cli.command()
    def freeze() -> None:
        freezer = Freezer(app)
        app.logger.info('Freezing to "%s"', app.config['OUTPUT_DIRECTORY'])
        freezer.freeze()

    return app
