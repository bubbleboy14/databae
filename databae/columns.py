import sqlalchemy
from sqlalchemy.dialects import mysql as mysqldialect
from .types import DynamicType, StringType, DateTimeAutoStamper, JSONType
from .types import basicType, BasicDT, BasicString, BasicText, BasicInt, BasicBig
from .keys import ArrayType, KeyWrapper, Key, IndexKey
from .blob import BlobWrapper, Blob

def _col(colClass, *args, **kwargs):
	cargs = {}
	indexed = kwargs.pop("indexed", False)
	unsigned = kwargs.pop("unsigned", False)
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
	if unsigned:
		variant = getattr(mysqldialect, colClass.impl.__name__)
		typeInstance.with_variant(variant(unsigned=True), "mysql")
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

primis = ["Float", "Boolean", "Text", "Date", "Time"]

for prop in primis:
	sqlprop = getattr(sqlalchemy, prop)
	globals()["sql%s"%(prop,)] = sqlprop
	globals()[prop] = sqlColumn(basicType(sqlprop))

Int = sqlColumn(BasicInt)
Big = sqlColumn(BasicBig)
String = sqlColumn(BasicString)
DateTime = sqlColumn(DateTimeAutoStamper)
JSON = sqlColumn(JSONType)
Binary = sqlColumn(Blob)
CompositeKey = sqlColumn(Key)
FlexForeignKey = sqlColumn(Key)
IndexForeignKey = sqlColumn(IndexKey)