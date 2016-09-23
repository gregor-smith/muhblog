import os
import functools
import subprocess
from pathlib import Path
from datetime import datetime

import click
import flask
import symlink

from . import database
from . import app, freezer, CONFIG_FILE, WINDOWS

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

def push_frozen_git(message=None):
    run = functools.partial(subprocess.run,
                            cwd=app.config['FREEZER_DESTINATION'])
    run(['git', 'add', '.'])
    run(['git', 'commit', '-am', message])
    run(['git', 'push'])

@main.command()
@click.option('-m', '--message',
              default=lambda: 'push called at {}'.format(datetime.now()))
def push(message):
    push_frozen_git(message)

@main.command()
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
@click.option('--url', default=lambda: app.config['BLOG_URL'])
@click.option('--push', is_flag=True)
@click.option('--overwrite', is_flag=True)
@click.option('--rename', is_flag=True)
@click.option('--clipboard', is_flag=True)
def upload(path, url, push, overwrite, rename, clipboard):
    path = Path(path).absolute()
    if rename:
        name = str(int(datetime.now().timestamp())) + path.suffix
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

    if push:
        freezer.freeze()
        push_frozen_git('uploaded {} at {}'.format(name, datetime.now()))
    if url is not None:
        with app.test_request_context():
            file_url = url + flask.url_for('uploads_view', filename=name)
        print(file_url)
        if clipboard:
            subprocess.run(['clip' if WINDOWS else 'xclip'],
                           input=file_url, universal_newlines=True)

@main.command()
@click.option('--freeze', is_flag=True)
@click.option('--host')
@click.option('--port', type=int, default=9001, show_default=True)
@click.option('--debug', is_flag=True)
def run(freeze, **kwargs):
    (freezer if freeze else app).run(**kwargs)
