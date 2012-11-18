'''
Bottle-peewee is a plugin that integrates Peewee with your Bottle
application. It automatically connects to a database at the beginning of a
request, passes the database handle to the route callback and closes the
connection afterwards.

To automatically detect routes that need a database connection, the plugin
searches for route callbacks that require a `db` keyword argument
(configurable) and skips routes that do not. This removes any overhead for
routes that don't need a database connection.

Usage Example::

	import bottle
	import peewee
	from peewee import *
	from bottle_peewee import Database, Plugin

	app = bottle.Bottle()

	db = Database('db/sample.db', 'peewee.SqliteDatabase', autocommit=False)

	class BaseModel(Model):
	    class Meta:
		database = db.database

	class User(BaseModel):
		name = CharField()

	User.create_table(fail_silently=True)

	User.create(name='A')
	User.create(name='B')
	User.create(name='C')

	plugin = Plugin(db)
	app.install(plugin)

	@app.route('/')
	def index(db):
		users = User.select()
		result = "".join(["<li>%s</li>" % user.name for user in users])
		return "Here is:<br><ul>%s</ul>" % result


	if __name__ == '__main__':
	    bottle.debug(True)
	    bottle.run(app, reloader=True)
'''

__author__ = "Indra Gunawan"
__version__ = '0.1'
__license__ = 'MIT'

### CUT HERE (see setup.py)

import sys
import peewee
from peewee import *
import inspect
from bottle import HTTPResponse, HTTPError
import bottle

def load_class(s):
    path, klass = s.rsplit('.', 1)
    __import__(path)
    mod = sys.modules[path]
    return getattr(mod, klass)


class Database(object):

    def __init__(self, db_name, db_engine, autocommit=True):
        self.database_config = {'name': db_name, 'engine': db_engine, 'autocommit': autocommit}
        try:
            self.database_name = self.database_config.pop('name')
            self.database_engine = self.database_config.pop('engine')
            self.autocommit = self.database_config.get('autocommit')
        except KeyError:
            raise ImproperlyConfigured('Please specify a "name" and "engine" for your database')
        
        try:
            self.database_class = load_class(self.database_engine)
            assert issubclass(self.database_class, peewee.Database)
        except ImportError:
            raise ImproperlyConfigured('Unable to import: "%s"' % self.database_engine)
        except AttributeError:
            raise ImproperlyConfigured('Database engine not found: "%s"' % self.database_engine)
        except AssertionError:
            raise ImproperlyConfigured('Database engine not a subclass of peewee.Database: "%s"' % self.database_engine)

        self.database = self.database_class(self.database_name, **self.database_config)
        self.Model = self.get_model_class()


    def get_model_class(self):
        class BaseModel(Model):
            class Meta:
                database = self.database

        return BaseModel


class PeeweePlugin(object):
    ''' This plugin passes an Peewee database handle to route callbacks
    that accept a `db` keyword argument. If a callback does not expect
    such a parameter, no connection is made. You can override the database
    settings on a per-route basis. '''

    name = 'peewee'
    api = 2

    def __init__(self, db, keyword='db'):
       self.db = db 
       self.keyword = keyword

    def setup(self, app):
        ''' Make sure that other installed plugins don't affect the same
            keyword argument.'''
        for other in app.plugins:
            if not isinstance(other, PeeweePlugin): continue
            if other.keyword == self.keyword:
                raise PluginError("Found another peewee plugin with "\
                "conflicting settings (non-unique keyword).")

    def apply(self, callback, context):
        # Override global configuration with route-specific values.
        
        # print 'VERSION:', bottle.__version__
        # if bottle.__version__.startswith('0.9'):
        #     conf = context['config']
        # else:
        #     conf = context.config
        #conf = context['config'].get('peewee') or {}

        conf = context.config
        db = conf.get('db', self.db)
        keyword = conf.get('keyword', self.keyword)

        # print 'AUTOCOMMIT:', db.autocommit

        # Test if the original callback accepts a 'db' keyword.
        # Ignore it if it does not need a database handle.
        # args = inspect.getargspec(context['callback'])[0]
        args = inspect.getargspec(context.callback) [0]
        if keyword not in args:
            return callback

        def wrapper(*args, **kwargs):
            # Connect to the database
            print 'CONNECT()'
            db.database.connect()
            # Add the connection handle as a keyword argument.
            kwargs[keyword] = db

            try:
                rv = callback(*args, **kwargs)
                if db.autocommit: db.database.commit()
            # except HTTPError, e:
            #     raise
            # except HTTPResponse, e:
            #     if db.autocommit: db.database.commit()
            #     raise
            except Exception, e:
                db.database.rollback()
                raise HTTPError(500, "Database Error: %s" % str(e), e)
            finally:
                db.database.close()
                print 'DISCONNECT()'
            return rv

        # Replace the route callback with the wrapped one.
        return wrapper

Plugin = PeeweePlugin