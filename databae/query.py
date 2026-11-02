from time import sleep
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import UnboundExecutionError
from sqlalchemy.sql import func, elements, visitors
from fyg.util import log, start_timer, end_timer
from fyg import config as confyg
from .properties import *
from .getters import *
from .setters import *
from .session import seshman, testSession, metadata, Session, handle_error, connection_error, set_scoper, indexer

_passthru = ["count", "all"]
_qmod = ["filter", "limit", "offset", "join"]

class Query(object):
    def __init__(self, mod, *args, **kwargs):
        self.mod = mod
        self.schema = get_schema(mod)
        self.cols = kwargs.pop("cols", None)
        if self.cols and type(self.cols[0]) is str:
            self.cols = [getattr(self.mod, c) for c in self.cols]
        self.session = seshman.get(kwargs.pop("session", "main"))
        sq = self.session.query
        self.query = kwargs.pop("query", None) or (self.cols and sq(*self.cols) or sq(mod))
        for fname in _passthru:
            setattr(self, fname, self._qpass(fname))
        for fname in _qmod:
            setattr(self, fname, self._qmlam(fname))
        self.get = self._qpass("first")
        self._order = self._qmlam("order_by")
        self.filter(*args, **kwargs)

    def order(self, prop):
        if type(prop) == elements.UnaryExpression and "count" not in prop.element.description:
            prop = "-%s"%(prop.element.description,)
        if isinstance(prop, str):
            asc = False
            if prop.startswith("-"):
                prop = prop[1:]
            else:
                asc = True
            if "." in prop: # foreignkey reference from another table
                from .lookup import refcount_subq
                sub = refcount_subq(prop, self.session)
                order = sub.c.count
                if not asc:
                    order = -sub.c.count
                return self.join(sub, self.mod.key == sub.c.target).order(order)
            prop = getattr(self.mod, prop)
            if not asc:
                prop = prop.desc()
        return self._order(prop)

    def _qpass(self, fname):
        def qp(*args, **kwargs):
            qkey = "Query.%s: %s %s (%s)"%(fname, args, kwargs, self.query)
            timed = "query" in confyg.log.allow
            session = self.query.session
            statement = self.query.statement
            # invalidate() permanently closes close_resets_only=False sessions.
            # SQLAlchemy has no public getter for this flag; unknown states do not retry.
            reusable = getattr(getattr(session, "_close_state", None), "name", None) == "CLOSE_IS_RESET"
            # Even a SELECT may autoflush writes or depend on earlier work.
            # Retrying is limited to an independent read on an empty session.
            try:
                safe_read = (reusable and isinstance(session.get_bind(clause=statement), Engine) and
                    not session.in_transaction() and not session.new and
                    not session.dirty and not session.deleted and not session.identity_map and
                    getattr(statement, "is_select", False) and
                    all(not getattr(part, "is_dml", False) and
                        getattr(part, "_for_update_arg", None) is None
                        for part in visitors.iterate(statement)))
            except UnboundExecutionError:
                # Let execution report the error through the normal application hook.
                safe_read = False
            retries = max(0, int(config.retry.reads)) if safe_read else 0
            delay = max(0, float(config.retry.delay)) if retries else 0
            flushed = False
            def before_flush(*unused):
                nonlocal flushed
                flushed = True
            if retries:
                event.listen(session, "before_flush", before_flush)
            attempt = 0
            repaired = False
            if timed:
                start_timer(qkey)
            try:
                while True:
                    try:
                        return getattr(self.query, fname)(*args, **kwargs)
                    except Exception as e:
                        disconnected = connection_error(e, session)
                        handle_error(e, session,
                            retry=disconnected and not flushed and not session.new and
                                not session.dirty and not session.deleted and attempt < retries,
                            repair=not repaired)
                        if disconnected:
                            attempt += 1
                            log("retrying database read %s of %s"%(attempt, retries))
                            sleep(delay * 2 ** (attempt - 1))
                        else:
                            # Preserve the existing one-retry missing-column repair.
                            repaired = True
                            log("retrying query operation after schema repair")
            finally:
                if retries:
                    event.remove(session, "before_flush", before_flush)
                if timed:
                    end_timer(qkey)
        return qp

    def _qmlam(self, fname):
        return lambda *a, **k : self._qmod(fname, *a, **k)

    def _qmod(self, modname, *args, **kwargs):
        self.query = getattr(self.query, modname)(*args, **kwargs)
        return self

    def copy(self, *args, **kwargs):
        kwargs["query"] = self.query
        return Query(self.mod, *args, **kwargs)

    def fetch(self, limit=None, offset=0, keys_only=False):
        if limit:
            self.limit(limit)
        if offset:
            self.offset(offset)
        res = self.all()
        if keys_only: # best way?
            return [r.key for r in res]
        return res
