import os
from pathlib import Path
from datetime import datetime

import click
import symlink

from . import database
from . import app, freezer, CONFIG_FILE

@click.group()
@click.option('--config-path', envvar='BLOG_CONFIG_PATH',
              type=click.Path(dir_okay=False, exists=True),
              default=os.fspath(CONFIG_FILE))
def main(config_path):
    app.config.from_json(config_path, silent=True)
    database.create_and_populate()

@main.command()
def freeze():
    freezer.freeze()

@main.command()
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
@click.option('--overwrite', is_flag=True)
@click.option('--rename', is_flag=True)
def upload(path, overwrite, rename):
    path = Path(path).absolute()
    if rename:
        name = str(round(path.stat().st_mtime * 1000)) + path.suffix
    else:
        name = path.name
    destination = Path(app.config['BLOG_USER_UPLOADS_DIR'], name)
    if destination.exists():
        if overwrite:
            destination.unlink()
        else:
            raise SystemExit('path already exists: {}'.format(destination))

    link_type = symlink.link(destination, path, copy_fallback=True)
    if link_type is symlink.LinkType.symlink:
        print('symlink created:', destination)
    elif link_type is symlink.LinkType.hardlink:
        print('hardlink created:', destination)
    else:
        print('copy created:', destination)

@main.command()
@click.option('--freeze', is_flag=True)
@click.option('--host')
@click.option('--port', type=int, default=9001, show_default=True)
@click.option('--debug', is_flag=True)
def run(freeze, **kwargs):
    (freezer if freeze else app).run(**kwargs)
