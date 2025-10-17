from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.schema import CreateTable
from .query import *

def choice_validator(choices):
    def cval(s, k, v):
        if v not in choices:
            error("can't set %s! %s not in %s"%(k, v, choices))
        return v
    return cval

class BasicMeta(DeclarativeMeta):
    def query(cls, *args, **kwargs):
        return Query(cls, *args, **kwargs)

    def creationSQL(cls, recursive=False):
        csql = str(CreateTable(cls.__table__).compile(seshman.get().engine))
        if not recursive:
            return csql
        psgen = getattr(cls.__base__, "creationSQL", None)
        base = psgen(True) if psgen else []
        return base + [csql]

    def _prepAttrs(cls, attrs, bases):
        if "label" not in attrs:
            for label in ["name", "title", "topic"]:
                if label in attrs:
                    attrs["label"] = label
                    break
        schema = attrs["_schema"] = merge_schemas(bases, attrs.get("label"))
        for key, val in list(attrs.items()):
            if getattr(val, "_ct_type", None):
                schema[key] = val._ct_type
                if val._ct_type.startswith("key"):
                    schema["_kinds"][key] = val._kinds
                if getattr(val, "_indexed", None):
                    indexer.index(lname, key)
            if getattr(val, "choices", None):
                attrs["%s_validator"%(key,)] = sqlalchemy.orm.validates(key)(choice_validator(val.choices))

    def __new__(cls, name, bases, attrs):
        lname = name.lower()
        attrs["__tablename__"] = lname
        modelsubs[lname] = super(BasicMeta, cls).__new__(cls, name, bases, attrs)
        modelsubs[lname].__name__ = lname
        return modelsubs[lname]

class FlatMeta(BasicMeta):
    def __new__(cls, name, bases, attrs):
        lname = name.lower()
        if lname != "flatbase":
            attrs["index"] = Integer(primary_key=True)
            attrs["key"] = CompositeKey(length=config.flatkeysize)
            BasicMeta._prepAttrs(cls, attrs, bases)
        return super(FlatMeta, cls).__new__(cls, name, bases, attrs)

class PolyMeta(BasicMeta):
    def __new__(cls, name, bases, attrs):
        lname = name.lower()
        if lname != "modelbase":
            attrs["__mapper_args__"] = {
                "polymorphic_identity": lname
            }
            attrs["index"] = sqlForeignKey(bases[0], primary_key=True)
            BasicMeta._prepAttrs(cls, attrs, bases)
        return super(PolyMeta, cls).__new__(cls, name, bases, attrs)

DeclarativeBase = declarative_base(metadata=metadata)