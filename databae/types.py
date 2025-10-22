import sqlalchemy, json
from .config import config

primis = ["BIGINT", "Float", "Boolean", "Text", "Date", "Time"]

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
	attrs = { "impl": colClass, "cache_ok": config.cache }
#	if config.cache and cname in primis:
#		attrs["cache_ok"] = True
	return type("%s"%(cname,), (baseType,), attrs)

BasicDT = basicType(sqlalchemy.DateTime)
BasicString = basicType(sqlalchemy.VARCHAR, StringType)
BasicText = basicType(sqlalchemy.UnicodeText)
BasicInt = basicType(sqlalchemy.Integer)

class DateTimeAutoStamper(BasicDT):
	cache_ok = config.cache

	def __init__(self, *args, **kwargs):
		self.auto_now = kwargs.pop("auto_now", False)
		self.auto_now_add = kwargs.pop("auto_now_add", False)
		BasicDT.__init__(self, *args, **kwargs)

	def should_stamp(self, is_new):
		return self.auto_now or is_new and self.auto_now_add

class JSONType(BasicText):
	def process_bind_param(self, value, dialect):
		return json.dumps(value)

	def process_result_value(self, value, dialect):
		return json.loads(value or "{}")