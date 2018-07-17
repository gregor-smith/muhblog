from peewee import SqliteDatabase, Model


database = SqliteDatabase(
    database='file:cachedb?mode=memory&cache=shared',
    uri=True,
    pragmas=[('foreign_keys', 'ON'), ('journal_mode', 'WAL')]
)


class BaseModel(Model):
    class Meta:
        database = database
