from typing import Iterable, DefaultDict, List
from collections import defaultdict

from flask import Blueprint, Response, abort

from .models import Entry, Tag, EntryTag, AboutPage
from .utils import Paginator, template_response


blueprint = Blueprint(
    name='controllers',
    import_name=__name__,
    static_folder='static',
    template_folder='views'
)


@blueprint.route('/', defaults={'page': 1})
@blueprint.route('/page/<int:page>/')
def front(page: int) -> Response:
    entries = Entry.select() \
        .order_by(Entry.date.desc())
    if not entries.count():
        abort(404)
    return template_response(
        'front.html',
        title=None,
        paginator=Paginator(query=entries, current_page=page)
    )


def _archive_response(entries: Iterable[Entry], title: str) -> Response:
    groups: DefaultDict[int, DefaultDict[int, DefaultDict[int, List[Entry]]]] = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(list)
        )
    )
    for entry in entries:
        groups[entry.date.year][entry.date.month][entry.date.day].append(entry)
    if not groups:
        abort(404)
    return template_response('archive.html', title=title, entries=groups)


@blueprint.route('/archive/')
def archive() -> Response:
    entries: Iterable[Entry] = Entry.select() \
        .iterator()
    return _archive_response(entries, title='archive')


@blueprint.route('/<year>/')
def archive_by_year(year: str) -> Response:
    entries: Iterable[Entry]
    try:
        entries = Entry.select() \
            .where(Entry.date.year == int(year)) \
            .iterator()
    except ValueError:
        abort(404)
    return _archive_response(entries, title=year)


@blueprint.route('/<year>/<month>/')
def archive_by_month(year: str, month: str) -> Response:
    entries: Iterable[Entry]
    try:
        entries = Entry.select() \
            .where(Entry.date.year == int(year)) \
            .where(Entry.date.month == int(month)) \
            .iterator()
    except ValueError:
        abort(404)
    return _archive_response(entries, title=f'{month}/{year}')


@blueprint.route('/<year>/<month>/<day>/')
def archive_by_day(year: str, month: str, day: str) -> Response:
    entries: Iterable[Entry]
    try:
        entries = Entry.select() \
            .where(Entry.date.year == int(year)) \
            .where(Entry.date.month == int(month)) \
            .where(Entry.date.day == int(day)) \
            .iterator()
    except ValueError:
        abort(404)
    return _archive_response(entries, title=f'{day}/{month}/{year}')


@blueprint.route('/tag/<slug>/')
def archive_by_tag(slug: str) -> Response:
    tag_name: str
    try:
        tag_name = Tag.get(slug=slug) \
            .name
    except Tag.DoesNotExist:
        abort(404)
    entries: Iterable[Entry] = Entry.select() \
        .join(EntryTag, on=Entry.id == EntryTag.entry_id) \
        .join(Tag, on=EntryTag.definition_id == Tag.id) \
        .where(Tag.slug == slug) \
        .iterator()
    return _archive_response(entries, title=tag_name)


@blueprint.route('/<year>/<month>/<day>/<slug>/')
def entry(year: str, month: str, day: str, slug: str) -> Response:
    entry: Entry
    try:
        entry = Entry.select() \
            .where(Entry.date.year == int(year)) \
            .where(Entry.date.month == int(month)) \
            .where(Entry.date.day == int(day)) \
            .where(Entry.slug == slug) \
            .get()
    except (ValueError, Entry.DoesNotExist):
        abort(404)
    return template_response('entry.html', title=entry.title, entry=entry)


@blueprint.route('/about/')
def about() -> Response:
    return template_response(
        'about.html',
        title='about',
        entry=AboutPage.get()
    )
