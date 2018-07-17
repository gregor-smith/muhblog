import collections

import flask

from .models import Entry, TagDefinition, TagMapping, AboutPage
from .utils import send_configurable_file, Paginator, render_template

blueprint = flask.Blueprint(
    name='controllers',
    import_name=__name__,
    static_folder='static',
    template_folder='templates'
)


@blueprint.route('/', defaults={'page': 1})
@blueprint.route('/page/<int:page>/')
def front(page):
    entries = Entry.select() \
        .order_by(Entry.date.desc())
    if not entries.count():
        flask.abort(404)
    return render_template('front.html', title=None,
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
            try:
                filtr = Entry.date.year == int(year)
            except ValueError:
                flask.abort(404)
            title = year
            if month is not None:
                filtr &= Entry.date.month == int(month)
                title = f'{month}/{year}'
                if day is not None:
                    filtr &= Entry.date.day == int(day)
                    title = f'{day}/{month}/{year}'
            entries = Entry.select() \
                .where(filtr)

    groups = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: collections.defaultdict(list)
        )
    )
    for entry in entries:
        groups[entry.date.year][entry.date.month][entry.date.day].append(entry)

    if not groups:
        flask.abort(404)
    return render_template('archive.html', title=title, entries=groups)


@blueprint.route('/<year>/<month>/<day>/<slug>/')
def entry(year, month, day, slug):
    try:
        entry = Entry.get(
            Entry.date.year == int(year),
            Entry.date.month == int(month),
            Entry.date.day == int(day),
            Entry.slug == slug
        )
    except (ValueError, Entry.DoesNotExist):
        flask.abort(404)
    return render_template('entry.html', entry=entry, title=entry.title)


@blueprint.route('/about/')
def about():
    return render_template('about.html', title='about', entry=AboutPage.get())


@blueprint.route('/stylesheet.css')
def stylesheet():
    return send_configurable_file(config_key='BLOG_STYLESHEET_PATH',
                                  mimetype='text/css',
                                  fallback='defaults/stylesheet.css')


@blueprint.route('/robots.txt')
def robots_txt():
    return send_configurable_file(config_key='BLOG_ROBOTS_TXT_PATH',
                                  mimetype='text/plain',
                                  fallback='defaults/robots.txt')


@blueprint.route('/favicon.png')
def favicon():
    return send_configurable_file(config_key='BLOG_FAVICON_PATH',
                                  mimetype='image/png',
                                  fallback='defaults/favicon.png')
