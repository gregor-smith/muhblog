import re
from datetime import datetime

from flask import Markup
from slugify import slugify
from peewee import TextField, DateTimeField, ForeignKeyField, CharField

from . import markdown
from .database import BaseModel

SLUG_LENGTH = 100
SNUB_LENGTH = 300
DATE_FORMAT = '%Y-%m-%d %H:%M'


class MarkdownModel(BaseModel):
    text = TextField()

    def render_markdown(self) -> Markup:
        return markdown.render(self.text)


class Entry(MarkdownModel):
    slug = CharField(unique=True, max_length=SLUG_LENGTH)
    title = CharField()
    date = DateTimeField()

    @classmethod
    def create(cls, text: str) -> 'Entry':
        metadata, text = markdown.parse_metadata(text)

        instance = cls(
            slug=slugify(
                metadata['title'],
                max_length=SLUG_LENGTH
            ),
            title=metadata['title'],
            date=datetime.strptime(metadata['date'], DATE_FORMAT),
            text=text
        )
        instance.save()
        for tag in metadata['tags']:
            EntryTag.create(entry=instance, name=tag)

        return instance

    def render_snub(self) -> str:
        snub = re.search(rf'^(.{{1,{SNUB_LENGTH}}}[\.\!\?])', self.text) \
            .group(1)
        return markdown.render(snub)


class AboutPage(MarkdownModel):
    @classmethod
    def create(cls, text: str) -> 'AboutPage':
        return super().create(text=text)


class Tag(BaseModel):
    slug = CharField(unique=True, max_length=SLUG_LENGTH)
    name = TextField()

    @classmethod
    def create(cls, name: str) -> 'Tag':
        return super().create(
            name=name,
            slug=slugify(name, max_length=SLUG_LENGTH)
        )


class EntryTag(BaseModel):
    definition = ForeignKeyField(Tag, backref='entries')
    entry = ForeignKeyField(Entry, backref='tags')

    @classmethod
    def create(cls, entry: Entry, name: str) -> 'EntryTag':
        return super().create(
            entry=entry,
            definition=Tag.get_or_create(name=name)[0]
        )
