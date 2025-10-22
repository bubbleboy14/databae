import sqlalchemy
from .types import primis, DynamicType, StringType, basicType
from .types import BasicDT, BasicString, BasicText, BasicInt, DateTimeAutoStamper, JSONType
from .keys import ArrayType, KeyWrapper, Key, IndexKey
from .blob import BlobWrapper, Blob
from .getters import get
from .config import config

def _col(colClass, *args, **kwargs):
	cargs = {}
	indexed = "indexed" in kwargs
	indexed and kwargs.pop("indexed")
	if "primary_key" in kwargs:
		cargs["primary_key"] = kwargs.pop("primary_key")
	default = kwargs.pop("default", None)
	if kwargs.pop("repeated", None):
		isKey = kwargs["isKey"] = colClass is Key
		typeInstance = ArrayType(**kwargs)
		col = sqlalchemy.Column(typeInstance, *args, **cargs)
		col._ct_type = isKey and "keylist" or "list"
		if isKey:
			col._kinds = typeInstance.kinds
		return col
	typeInstance = colClass(**kwargs)
	col = sqlalchemy.Column(typeInstance, *args, **cargs)
	col._indexed = indexed
	if hasattr(typeInstance, "choices"):
		col.choices = typeInstance.choices
	if colClass is DateTimeAutoStamper:
		col.is_dt_autostamper = True
		col.should_stamp = typeInstance.should_stamp
		col._ct_type = "datetime"
	elif colClass is BasicString:
		col._ct_type = "string"
	elif colClass is Key:
		col._kinds = typeInstance.kinds
	elif colClass is IndexKey:
		col._kind = typeInstance.kind
	elif colClass is JSONType:
		col._ct_type = "json"
	if not hasattr(col, "_ct_type"):
		col._ct_type = colClass.__name__.lower()
	col._default = default
	return col

def sqlColumn(colClass):
	return lambda *args, **kwargs : _col(colClass, *args, **kwargs)

for prop in primis:
	sqlprop = getattr(sqlalchemy, prop)
	globals()["sql%s"%(prop,)] = sqlprop
	globals()[prop] = sqlColumn(basicType(sqlprop))

DateTime = sqlColumn(DateTimeAutoStamper)
String = sqlColumn(BasicString)
JSON = sqlColumn(JSONType)
Binary = sqlColumn(Blob)
CompositeKey = sqlColumn(Key)
FlexForeignKey = sqlColumn(Key)
IndexForeignKey = sqlColumn(IndexKey)

def fkprop(targetClass):
	tname = targetClass if type(targetClass) is str else targetClass.__tablename__
	return sqlalchemy.ForeignKey("%s.index"%(tname,))

def sqlForeignKey(targetClass, **kwargs):
	return sqlalchemy.Column(sqlInteger, fkprop(targetClass), **kwargs)

def ForeignKey(**kwargs):
	if config.indexkeys: # single-kind, non-repeating!
		return IndexForeignKey(fkprop(kwargs.get("kind")), **kwargs)
	else:
		return FlexForeignKey(**kwargs)