import re
from datetime import datetime

import flask
import peewee
from slugify import slugify

from . import markdown
from .database import db


Model = db.get_model_base_class()


class MarkdownModel(Model):
    text = peewee.TextField()

    def convert_text(self):
        return markdown.convert(self.text)


class Entry(MarkdownModel):
    title = peewee.TextField()
    slug = peewee.TextField(unique=True)
    date = peewee.DateTimeField()

    @classmethod
    def create(cls, path):
        with open(path, encoding='utf-8') as file:
            metadata, text = markdown.parse_metadata(file.read())

        instance = cls(
            title=metadata['title'],
            slug=slugify(
                metadata['title'],
                max_length=flask.current_app.config['BLOG_SLUG_LENGTH_CHARACTERS']
            ),
            date=datetime.strptime(metadata['date'], '%Y-%m-%d %H:%M'),
            text=text
        )
        instance.save()
        for tag in metadata['tags']:
            TagMapping.create(entry=instance, name=tag)

        return instance

    def convert_snub(self):
        length = flask.current_app.config['BLOG_SNUB_LENGTH_CHARACTERS']
        snub = re.search(rf'^(.{{1,{length}}}[\.\!\?])', self.text) \
            .group(1)
        return markdown.convert(snub)

    def url(self):
        return flask.url_for('site.entry', year=self.date.year,
                             month=f'{self.date.month:0>2}',
                             day=f'{self.date.day:0>2}', slug=self.slug)


class AboutPage(MarkdownModel):
    @classmethod
    def create(cls, path):
        with open(path, encoding='utf-8') as file:
            return super().create(text=file.read())

    @classmethod
    def create_default(cls):
        super().create(
            text='No `about.md` was found in `BLOG_USER_STATIC_DIRECTORY`'
        )


class TagDefinition(Model):
    name = peewee.TextField()
    slug = peewee.TextField(unique=True)

    @classmethod
    def create(cls, name):
        return super().create(name=name, slug=slugify(name))

    def url(self):
        return flask.url_for('site.archive', slug=self.slug)


class TagMapping(Model):
    definition = peewee.ForeignKeyField(TagDefinition, related_name='mappings')
    entry = peewee.ForeignKeyField(Entry, related_name='tags')

    class Meta:
        constraints = [peewee.SQL('UNIQUE(definition_id, entry_id)')]

    @classmethod
    def create(cls, entry, name):
        return super().create(
            entry=entry,
            definition=TagDefinition.get_or_create(name=name)[0]
        )
