import peewee


class Database:
    def __init__(self):
        self._model_class = None
        self._database = peewee.Proxy()

    @property
    def Model(self):
        if self._model_class is None:
            class ModelBase(peewee.Model):
                class Meta:
                    database = self._database
            self._model_class = ModelBase
        return self._model_class

    def init_app(self, app):
        sqlite = peewee.SqliteDatabase(
            database=app.config['BLOG_DATABASE_PATH'],
            journal_mode='WAL',
            pragmas=[('foreign_keys', 'ON'),
                     ('cache_size', app.config['BLOG_DATABASE_CACHE_SIZE'])]
        )
        self._database.initialize(sqlite)

        app.before_request(self._connect_to_database)
        app.teardown_request(self._close_database)

    def _connect_to_database(self):
        self._database.connect()

    def _close_database(self, exception):
        if not self._database.is_closed():
            self._database.close()

    def atomic(self):
        return self._database.atomic()

    def create_tables(self, *model_classes):
        self._database.create_tables(model_classes)


db = Database()
