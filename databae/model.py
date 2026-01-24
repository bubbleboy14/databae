from sqlalchemy import orm
from fyg.util import log, error
from .meta import *

class ModelCore(DeclarativeBase):
    __abstract__ = True
    label = "key"
    _data_omit = []
    _unique_cols = []

    def __init__(self, *args, **kwargs):
        DeclarativeBase.__init__(self, *args, **kwargs)
        self._defaults()
        self._init()

    @orm.reconstructor
    def _init(self):
        self._name = "%s(%s)"%(self.polytype, getattr(self, self.label))
        self._orig_fkeys = {}
        for prop in self._schema["_kinds"]:
            self._orig_fkeys[prop] = getattr(self, prop)

    def _defaults(self):
        for prop in self._schema["_kinds"]:
            if getattr(self, prop, None) is None:
                if self._schema[prop].endswith("list"):
                    val = []
                else:
                    val = KeyWrapper()
                setattr(self, prop, val)
        if config.flatkeysize:
            self.key = KeyWrapper()
        for key, val in list(self.__class__.__dict__.items()):
            if getattr(self, key, None) is None and getattr(val, "_default", None) is not None:
                setattr(self, key, val._default)

    def __eq__(self, other):
        return self.id() == (other and hasattr(other, "id") and other.id())

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.key.__hash__()

    def put(self, session=None):
        try:
            put_multi([self], session)
        except Exception as e:
            handle_error(e, session, self.polytype, "has no column named")
            log("retrying put operation")
            put_multi([self], session)

    def otherwith(self, prop, val):
        k = self._schema[prop]
        c = self.__class__
        col = getattr(c, prop)
        q = c.query(c.key != self.key)
        print("checking", c.__name__, "for", prop, k, "=", val)
        if k.endswith("list"):
            for v in val:
                q.filter(col.contains(v))
        else:
            q.filter(col == val)
        return q.get()

    def beforeedit(self, edits):
        for prop in edits:
            if prop in self._unique_cols and self.otherwith(prop, edits[prop]):
                print(prop, "conflict!\n\n")
                return "%s must be unique"%(prop,)

    def beforeremove(self, session):
        pass

    def afterremove(self, session):
        pass

    def rm(self, commit=True, session=None):
        session = session or seshman.get()
        self.beforeremove(session)
        session.delete(self)
        commit and session.commit()
        self.afterremove(session)

    def collection(self, entity_model, property_name=None, fetch=True, keys_only=False, data=False):
        if isinstance(entity_model, str):
            entity_model = get_model(entity_model)
        q = entity_model.query(getattr(entity_model, property_name or self.polytype) == self.key)
        if not fetch:
            return q
        if not data:
            return q.fetch(1000, keys_only=keys_only)
        return [d.data() for d in q.fetch(1000)]

    def modeltype(self):
        return self.__tablename__

    def id(self):
        if not config.flatkeysize:
            return self.ival
        return self.key.urlsafe() if hasattr(self.key, "urlsafe") else self.key

    def _has_complete_key(self):
        return bool(self.id())

    def update(self, propmap):
        for key, val in propmap.items():
            setattr(self, key, val)

    def mydata(self, isexport=False):
        cols = {}
        for key, prop in list(self._schema.items()):
            if not isexport and key in self._data_omit:
                continue
            if not key.startswith("_"):
                val = getattr(self, key)
                if "key" in prop:
                    if type(val) is list:
                        val = [v.urlsafe() for v in val]
                    elif hasattr(val, "urlsafe"):
                        val = val.urlsafe()
                elif prop == "blob" and hasattr(val, "urlsafe"):
                    val = val.urlsafe()
                elif val and prop == "datetime":
                    val = str(val)[:19]
                elif val and prop == "date":
                    val = str(val)[:10]
                elif prop in ["string", "text"]:
                    val = val or ""
                cols[key] = val
        return cols

    @property
    def iname(self):
        return getattr(self, "indexname", "index")

    @property
    def ival(self):
        return getattr(self, self.iname)

    @property
    def ilabel(self):
        return "%s %s"%(self.polytype, self.ival)

    def labeler(self):
        if self.label == "key":
            return self.id()
        return getattr(self, self.label) or self.ilabel

    def _basic(self, d):
        if config.flatkeysize:
            d["key"] = self.id()
        d[self.iname] = self.ival
        d["modelName"] = self.polytype
        d["_label"] = self.label
        d["label"] = self.labeler()
        return d

    def data(self):
        return self._basic(self.mydata())

    def export(self):
        return self._basic(ModelCore.mydata(self, True))

class FlatBase(ModelCore, metaclass=FlatMeta):
    __abstract__ = True
    label = "ival"

    @property
    def polytype(self):
        return self.__class__.__name__