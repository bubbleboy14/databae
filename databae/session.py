import threading
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError, UnboundExecutionError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import create_engine, MetaData, text, event
from fyg.util import log, error, confirm, Loggy
from fyg import config as confyg
from .config import config as dcfg

pcfg = dcfg.pool
metadata = MetaData()

def slog(*msg):
	if "db" in confyg.log.allow:
		log("[db] session | %s"%(" ".join([str(m) for m in msg]),))

def conn_ex(cmd, fetch=False, commit=False, session="main"):
	log("issuing command: %s"%(cmd,), important=True)
	with seshman.get(session).engine.connect() as conn:
		result = conn.execute(text(cmd))
		if commit:
			conn.commit()
		if fetch:
			rows = result.fetchall()
	if fetch:
		return rows

class Indexer(Loggy):
	def __init__(self):
		self.indexes = {}
		self.pending = []

	def get(self, tname):
		if tname in self.indexes:
			return self.indexes[tname]
		iz = conn_ex("pragma index_list('%s')"%(tname,), True)
		self.indexes[tname] = [i[1] for i in iz]
		return self.indexes[tname]

	def index(self, tname, cname):
		iname = "idx_%s_%s"%(tname, cname)
		if iname not in self.get(tname):
			self.pending.append((iname, tname, cname))

	def flush(self):
		if not self.pending: return
		self.log("flush", len(self.pending), "indexes")
		for iname, tname, cname in self.pending:
			conn_ex("create index %s on %s(%s)"%(iname, tname, cname))
			self.indexes[tname].append(iname)
		self.pending = []

indexer = Indexer()

prags = {
	"fast": { # sqlite
		"journal_mode": "WAL",
		"synchronous": "normal"
	}
}

@event.listens_for(Engine, "connect")
def init_prags(dbapi_connection, connection_record):
	if not dcfg.prags: return
	cursor = dbapi_connection.cursor()
	ex = lambda s : cursor.execute(s)
	val = lambda s : ex(s).fetchall()[0][0]
	for p, v in prags[dcfg.prags].items():
		pstr = "PRAGMA %s"%(p,)
		prev = val(pstr)
		ex("%s = %s"%(pstr, v))
		slog("pragma", p, ":", prev, "->", val(pstr))
	cursor.close()

@event.listens_for(Engine, "close")
def optimize(dbapi_connection, connection_record):
	if not dcfg.optimize: return
	cursor = dbapi_connection.cursor()
	cursor.execute("PRAGMA optimize")
	slog("optimize")
	cursor.close()

def add_column(mod, col, colrep=None):
	log("adding '%s' to '%s'"%(col, mod))
	if colrep: # mysql style
		addcmd = 'ALTER TABLE %s ADD %s %s'%(mod, col, colrep)
	else: # sqlite style
		addcmd = 'ALTER TABLE "%s" ADD COLUMN "%s"'%(mod, col)
	conn_ex(addcmd)

def connection_error(e, session):
	if not isinstance(e, DBAPIError):
		return False
	if e.connection_invalidated:
		return True
	# A failed initial connection has no Connection for SQLAlchemy to invalidate.
	args = getattr(e.orig, "args", ())
	if not args or args[0] not in (2002, 2003, 2006, 2013, 2055):
		return False
	try:
		bind = session.get_bind()
	except UnboundExecutionError:
		return False
	return bind.dialect.name in ("mysql", "mariadb")

def reset_session(session, disconnect=False):
	try:
		if disconnect:
			session.invalidate()
		else:
			session.rollback()
		return True
	except Exception as cleanup_error:
		# Cleanup must not mask the error that interrupted the operation.
		log("Database session cleanup failed: %s"%(type(cleanup_error).__name__,))
		if not disconnect:
			try:
				session.invalidate()
				return True
			except Exception as invalidate_error:
				log("Database session invalidation failed: %s"%(type(invalidate_error).__name__,))
		return False

def handle_error(e, session="main", polytype=None, flag=" no such column: ", mysqlflag='Unknown column ', retry=False, repair=True):
	log("Database operation failed: %s"%(e,), important=True)
	import traceback
	log("".join(traceback.TracebackException.from_exception(e).format()))
	session = seshman.get(session)
	# Work directly with the current ORM session: the databae wrapper would run
	# database initialization again before rollback, which can itself need I/O.
	orm_session = session.session if isinstance(session, Session) else session
	if connection_error(e, orm_session):
		cleaned = reset_session(orm_session, disconnect=True)
		if retry and cleaned:
			return
		error(e)
		# A returning application error callback must not trigger write replay.
		raise e
	stre = str(e)
	colrep = None
	raise_anyway = True
	mysqladd = mysqlflag in stre
	if mysqladd:
		log("Missing MYSQL column!")
		flag = mysqlflag
	if repair and flag in stre:
		target = stre.split(flag)[1].split(None, 1)[0].strip("'")
		log("Missing column: %s"%(target,), important=True)
		if dcfg.alter:
			if "." in target:
				tmod, tcol = target.split(".")
			else:
				tcol = target
				tmod = polytype
			if dcfg.alter == "auto" or confirm("Add missing column '%s' to table '%s'"%(tcol, tmod), True):
				log("rolling back session")
				orm_session.rollback()
				raise_anyway = False
				if mysqladd:
					from .util import get_model
					coltype = get_model(tmod).__table__.columns[tcol].type
					colrep = coltype.compile(orm_session.get_bind().dialect)
				add_column(tmod, tcol, colrep)
		else:
			log("To auto-update columns, add 'DB_ALTER = True' to your ct.cfg", important=True)
	if raise_anyway:
		reset_session(orm_session)
		error(e)
		raise e

def threadname():
	return threading.currentThread().getName()

scoper = None

def set_scoper(func):
	global scoper
	scoper = func

class Basic(object): # move elsewhere?
	def sig(self):
		return "%s(%s)"%(self.__class__.__name__, self.id)

	def log(self, *msg):
		slog(self.sig(), "::", *msg)

class Session(Basic):
	def __init__(self, database):
		Session._id += 1
		self.id = Session._id
		self.database = database
		self.engine = database.engine
		self.generator = scoped_session(sessionmaker(bind=self.engine), scopefunc=self._scope)
		for fname in ["add", "add_all", "delete", "flush", "commit", "query", "rollback"]:
			setattr(self, fname, self._func(fname))
		self._refresh()
		self.log("initialized")

	def teardown(self):
		self.engine = None
		self.session = None
		self.database = None
		self.generator = None

	def _scope(self):
		threadId = threadname()
		return scoper and scoper(threadId) or threadId

	def _func(self, fname):
		def f(*args):
			self._refresh()
			self.database.init()
			return getattr(self.session, fname)(*args)
		return f

	def _refresh(self):
		self.session = self.generator()
		self.no_autoflush = self.session.no_autoflush

class DataBase(Basic):
	def __init__(self, db=dcfg.main):
		DataBase._id += 1
		self.id = DataBase._id
		tos = dcfg.timeout
		url = make_url(db)
		cargs = {}
		if url.get_backend_name() in ("mysql", "mariadb") and url.get_driver_name() == "pymysql":
			# Explicit URL settings override databae's defaults. Other drivers
			# (including SQLite) must not receive PyMySQL-specific arguments.
			cargs = {name + "_timeout": tos[name] for name in ("read", "write", "connect")
				if name + "_timeout" not in url.query}
		if pcfg.null:
			self.engine = create_engine(db, poolclass=NullPool,
				echo=dcfg.echo, connect_args=cargs)
		else:
			self.engine = create_engine(db, pool_size=pcfg.size,
				max_overflow=pcfg.overflow, pool_recycle=pcfg.recycle,
				echo=dcfg.echo, connect_args=cargs)
		self.sessions = {}
		self._ready = False
		self.log("initialized")

	def init(self):
		if not self._ready:
			self._ready = True
			metadata.create_all(self.engine)
			indexer.flush()

	def session(self):
		thread = threadname()
		if thread not in self.sessions:
			self.sessions[thread] = Session(self)
			self.log("session(%s) created!"%(thread,))
		return self.sessions[thread]

	def close(self):
		thread = threadname()
		if thread in self.sessions:
			self.sessions[thread].generator.remove()
			if thread == "MainThread":
				note = "released"
			else:
				self.sessions[thread].teardown()
				del self.sessions[thread]
				note = "deleted"
		else:
			note = "not found!"
		self.log("close(%s)"%(thread,), "session", note)

class SessionManager(Basic):
	def __init__(self):
		SessionManager._id += 1
		self.id = SessionManager._id
		self.dbs = {}
		self.log("initialized")

	def db(self, db="main"):
		db = dcfg[db] or db
		if db not in self.dbs:
			self.dbs[db] = DataBase(db)
		return self.dbs[db]

	def get(self, db="main"):
		if type(db) is not str:
			return db # it's probably already a session...
		return self.db(db).session()

	def close(self, db="main"):
		self.db(db).close()

Session._id = DataBase._id = SessionManager._id = 0

def testSession():
	return seshman.get("test")

seshman = SessionManager()
