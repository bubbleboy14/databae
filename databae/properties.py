import os, json, sqlalchemy
from .getters import get
from .config import config

primis = ["Integer", "Float", "Boolean", "Text", "Date", "Time"]

class DynamicType(sqlalchemy.TypeDecorator):
	cache_ok = config.cache

	def __init__(self, *args, **kwargs):
		self.choices = kwargs.pop("choices", None)
		sqlalchemy.TypeDecorator.__init__(self, *args, **kwargs)

class StringType(DynamicType):
	def __init__(self, *args, **kwargs):
		# len required for MySQL VARCHAR
		DynamicType.__init__(self, kwargs.pop("length", config.stringsize), *args, **kwargs)

def basicType(colClass, baseType=DynamicType):
	cname = colClass.__name__
	attrs = { "impl": colClass }
	if config.cache and cname in primis:
		attrs["cache_ok"] = True
	return type("%s"%(cname,), (baseType,), attrs)

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

# datetime
BasicDT = basicType(sqlalchemy.DateTime)
class DateTimeAutoStamper(BasicDT):
	cache_ok = config.cache

	def __init__(self, *args, **kwargs):
		self.auto_now = kwargs.pop("auto_now", False)
		self.auto_now_add = kwargs.pop("auto_now_add", False)
		BasicDT.__init__(self, *args, **kwargs)

	def should_stamp(self, is_new):
		return self.auto_now or is_new and self.auto_now_add

DateTime = sqlColumn(DateTimeAutoStamper)

# strings, arrays, keys
class BasicString(basicType(sqlalchemy.UnicodeText, StringType)):
	cache_ok = config.cache

	def process_bind_param(self, data, dialect):
#		if data and type(data) is not str:
#			data = data.decode('utf-8')
		return data

String = sqlColumn(BasicString)

class JSONType(BasicString):
	def process_bind_param(self, value, dialect):
		return json.dumps(value)

	def process_result_value(self, value, dialect):
		return json.loads(value or "{}")

JSON = sqlColumn(JSONType)

class BlobWrapper(object):
	def __init__(self, data="", value=0):
		self.value = value
		if data:
			self.set(data)
		else:
			self._set_path(value)

	def __nonzero__(self): # py2
		return bool(self.value)

	def __bool__(self): # py3
		return bool(self.value)

	def get(self):
		if self.value:
			from fyg.util import read
			return read(self.path, binary=True)
		else:
			return None

	def _next_value(self): # safely handles gaps
		p, d, f = next(os.walk(config.blob))
		fiz = [int(i) for i in f]
		fiz.sort()
		v = 1
		for n in fiz:
			if n != v:
				return v
			v += 1
		return len(fiz) + 1

	def _set_path(self, data=None):
		if data:
			if not self.value:
				self.value = self._next_value()
			self.path = os.path.join(config.blob, str(self.value))
		else:
			self.value = 0
			self.path = None

	def set(self, data):
		self._set_path(data)
		if data:
			from fyg.util import write
			if type(data) != bytes:
				data = data.encode()
			write(data, self.path, binary=True)

	def delete(self):
		if self.value:
			from fyg.util import rm
			rm(self.path)
			self._set_path()

	def urlsafe(self):
		return self.path and "/" + "/".join(os.path.split(self.path))

BasicInt = basicType(sqlInteger)

class Blob(BasicInt):
	def __init__(self, *args, **kwargs):
		self.unique = kwargs.pop("unique", False)
		BasicInt.__init__(self, *args, **kwargs)

	def process_bind_param(self, data, dialect):
		if type(data) is not BlobWrapper:
			if self.unique:
				from fyg.util import indir
				match = indir(data, config.blob)
				if match:
					return int(match)
			data = BlobWrapper(data)
		return data.value

	def process_result_value(self, value, dialect):
		return BlobWrapper(value=value)

Binary = sqlColumn(Blob)

"""
class Binary(basicType(sqlString)):
	def process_bind_param(self, value, dialect):
		return sqlalchemy.func.HEX(value)

	def process_result_value(self, value, dialect):
		return sqlalchemy.func.UNHEX(value)
"""

class ArrayType(BasicString):
	cache_ok = config.cache

	def __init__(self, *args, **kwargs):
		self.isKey = kwargs.pop("isKey", False)
		if self.isKey:
			self.kinds = kwargs.pop("kinds", [kwargs.pop("kind", "*")])
			for i in range(len(self.kinds)):
				if not isinstance(self.kinds[i], str):
					self.kinds[i] = self.kinds[i].__name__.lower()
		BasicString.__init__(self, *args, **kwargs)

	def process_bind_param(self, value, dialect):
		if self.isKey:
			for i in range(len(value)):
				if hasattr(value[i], "urlsafe"):
					value[i] = value[i].urlsafe()
		return json.dumps(value)

	def process_result_value(self, value, dialect):
		try:
			vlist = json.loads(value) or []
		except:
			vlist = []
		if self.isKey:
			for i in range(len(vlist)):
				vlist[i] = KeyWrapper(vlist[i])
		return vlist

class KeyWrapper(object):
	def __init__(self, urlsafe=None, model=None):
		self.value = urlsafe
		self.model = model

	def __nonzero__(self): # py2
		return bool(self.value)

	def __bool__(self): # py3
		return bool(self.value)

	def __eq__(self, other):
		return hasattr(other, "value") and self.value == other.value

	def __ne__(self, other):
		return not hasattr(other, "value") or self.value != other.value

	def __hash__(self):
		return self.value if type(self.value) is int else sum([ord(c) for c in self.value])

	def get(self, session=None):
		return get(self.value, session, self.model)

	def delete(self):
		ent = self.get()
		ent and ent.rm() # should be more efficient way...

	def urlsafe(self):
		return self.value

class Key(BasicString):
	cache_ok = config.cache

	def __init__(self, *args, **kwargs):
		self.kinds = kwargs.pop("kinds", [kwargs.pop("kind", "*")])
		for i in range(len(self.kinds)):
			if not isinstance(self.kinds[i], str):
				self.kinds[i] = self.kinds[i].__name__.lower()
		BasicString.__init__(self, *args, **kwargs)

	def process_bind_param(self, value, dialect):
		while True:#value and hasattr(value, "urlsafe"):
			try: # for sqlite weirdness -- do this cleaner?
				value = value.urlsafe()
			except:
				break
		return value

	def process_result_value(self, value, dialect):
		return KeyWrapper(value)

class IndexKey(BasicInt):
	cache_ok = config.cache

	def __init__(self, *args, **kwargs):
		self.kind = kwargs.pop("kind")
		if not isinstance(self.kind, str):
			self.kind = self.kind.__name__.lower()
		BasicInt.__init__(self, *args, **kwargs)

	def process_bind_param(self, value, dialect):
		return value

	def process_result_value(self, value, dialect):
		return KeyWrapper(value, self.kind)

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