import bottle
#from peeweee import Model
from peewee import *
import peewee
#from bottle.ext import peeweeeorm
from bottle_peewee import Database, Plugin

app = bottle.Bottle()

# db = peeweee.Database('db/sample.db', 'peewee.SqliteDatabase')
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
User.create(name='D')
User.create(name='E')
User.create(name='F')

# plugin = peeweee.Plugin(db)
plugin = Plugin(db)
app.install(plugin)

@app.route('/')
def index(db):
	"""
	This shoult OK because we have 'db' keyword that will auto*connect the DB via plugin
	"""
	print 'SELECT()'
	users = User.select()
	result = "".join(["<li>%s</li>" % user.name for user in users])
	return "Here is:<br><ul>%s</ul>" % result


@app.route('/xxx')
def xxx():
	"""
	This shoult error because DB is not autoconnect, but???
	"""
	print 'SELECT2()'
	users = User.select()
	result = "".join(["<li>%s</li>" % user.name for user in users])
	return "Here is:<br><ul>%s</ul>" % result

if __name__ == '__main__':
    bottle.debug(True)
    bottle.run(app, reloader=True)

