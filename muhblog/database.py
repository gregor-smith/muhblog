import peewee


class Database:
    def __init__(self):
        self._database = peewee.Proxy()

    def get_model_base_class(self):
        class ModelBase(peewee.Model):
            class Meta:
                database = self._database
        return ModelBase

    def init_app(self, app):
        sqlite = peewee.SqliteDatabase(
            database=app.config['BLOG_DATABASE_PATH'],
            journal_mode='WAL',
            pragmas=[('foreign_keys', 'ON')]
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
