import io
import collections
import math as maths

import flask
import pkg_resources

from .models import Entry, Upload, TagDefinition, TagMapping, AboutPage

blueprint = flask.Blueprint(name='site', import_name=__name__,
                            static_folder='static',
                            template_folder='templates')


class Paginator:
    def __init__(self, query, current_page):
        self.query = query
        self.current_page = current_page
        self.total_posts = self.query.count()

    def get_pages(self, page=None):
        return self.query.paginate(
            page or self.current_page,
            flask.current_app.config['BLOG_ENTRIES_PER_PAGE']
        )

    @property
    def total_pages(self):
        per_page = flask.current_app.config['BLOG_ENTRIES_PER_PAGE']
        return maths.ceil(self.total_posts / per_page)

    def has_previous_page(self):
        return self.current_page != 1

    def has_next_page(self):
        return self.current_page != self.total_pages

    def page_link_group(self, start=1, group_size=5):
        end = self.total_pages

        if end - start <= group_size:
            return range(start, end + 1)

        padding = group_size // 2
        group_start = self.current_page - padding
        group_end = self.current_page + padding

        if group_start < start:
            end_extra = start - group_start
            group_start = start
        else:
            end_extra = 0

        if group_end > end:
            start_extra = (0 if end_extra != 0 else (group_end - end))
            group_end = end
        else:
            start_extra = 0

        return range(group_start - start_extra, group_end + end_extra + 1)


@blueprint.route('/', defaults={'page': 1})
@blueprint.route('/page/<int:page>/')
def front(page):
    entries = Entry.select() \
        .order_by(Entry.date.desc())
    if not entries.count():
        flask.abort(404)
    return flask.render_template('front.html', title=None,
                                 paginator=Paginator(entries, page))


@blueprint.route('/archive/')
@blueprint.route('/<year>/')
@blueprint.route('/<year>/<month>/')
@blueprint.route('/<year>/<month>/<day>/')
@blueprint.route('/tag/<slug>/')
def archive(year=None, month=None, day=None, slug=None):
    if slug is not None:
        entries = Entry.select() \
            .join(TagMapping,
                  on=Entry.id == TagMapping.entry_id) \
            .join(TagDefinition,
                  on=TagMapping.definition_id == TagDefinition.id) \
            .where(TagDefinition.slug == slug)
        title = TagDefinition.get(slug=slug) \
            .name
    else:
        entries = Entry.select()
        title = 'archive'
        if year is not None:
            filter = Entry.date.year == int(year)
            title = year
            if month is not None:
                filter &= Entry.date.month == int(month)
                title = f'{month}/{year}'
                if day is not None:
                    filter &= Entry.date.day == int(day)
                    title = f'{day}/{month}/{year}'
            entries = Entry.select() \
                .where(filter)

    groups = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: collections.defaultdict(list)
        )
    )
    for entry in entries:
        groups[entry.date.year][entry.date.month][entry.date.day].append(entry)

    if not groups:
        flask.abort(404)
    return flask.render_template('archive.html', title=title, entries=groups)


@blueprint.route('/<year>/<month>/<day>/<slug>/')
def entry(slug, **kwargs):
    entry = Entry.get_or_abort(slug=slug)
    return flask.render_template('entry.html', entry=entry, title=entry.title)


@blueprint.route('/about/')
def about():
    return flask.render_template('about.html', title='about',
                                 entry=AboutPage.get())


def send_configurable_file(filename, config_key, mimetype):
    path = flask.current_app.config[config_key]
    if path is None:
        byts = pkg_resources.resource_string('muhblog', f'defaults/{filename}')
    else:
        with open(path, mode='rb') as file:
            byts = file.read()
    return flask.send_file(io.BytesIO(byts), mimetype=mimetype)


@blueprint.route('/stylesheet.css')
def stylesheet():
    return send_configurable_file(filename='stylesheet.css',
                                  config_key='BLOG_STYLESHEET_PATH',
                                  mimetype='text/css')


@blueprint.route('/robots.txt')
def robots_txt():
    return send_configurable_file(filename='robots.txt',
                                  config_key='BLOG_ROBOTS_TXT_PATH',
                                  mimetype='text/plain')


@blueprint.route('/favicon.png')
def favicon():
    return send_configurable_file(filename='favicon.png',
                                  config_key='BLOG_FAVICON_PATH',
                                  mimetype='image/png')


@blueprint.route('/uploads/')
@blueprint.route('/uploads/<path:filename>')
def uploads(filename=None):
    if filename is None:
        files = Upload.select() \
            .order_by(Upload.date_modified) \
            .desc()
        return flask.render_template(
            'uploads.html', files=files, title='uploads',
            scripts=[flask.url_for('static', filename='jquery.js'),
                     flask.url_for('static', filename='tablesorter.js'),
                     flask.url_for('static', filename='sort.js')]
        )
    return Upload.get_or_abort(name=filename) \
        .send()


@blueprint.route('/player/<path:filename>/')
def player(filename):
    upload = Upload.get_or_abort(name=filename)
    if not upload.requires_player():
        flask.abort(404)
    return flask.render_template('player.html', title=upload.name,
                                 upload=upload)
