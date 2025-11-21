import json
from .types import BasicString, BasicText
from .keys import KeyWrapper
from .config import config

class JSONBase(object):
	def process_bind_param(self, value, dialect):
		return json.dumps(value)

	def process_result_value(self, value, dialect):
		return json.loads(value or "{}")

class JSONText(JSONBase, BasicText):
	pass

class JSONString(JSONBase, BasicString):
	pass

class ArrayBase(object):
	cache_ok = config.cache

	def _keykinds(self, kwargs):
		self.isKey = kwargs.pop("isKey", False)
		if self.isKey:
			self.kinds = kwargs.pop("kinds", [kwargs.pop("kind", "*")])
			for i in range(len(self.kinds)):
				if not isinstance(self.kinds[i], str):
					self.kinds[i] = self.kinds[i].__name__.lower()

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

class ArrayText(ArrayBase, BasicText):
	def __init__(self, *args, **kwargs):
		self._keykinds(kwargs)
		BasicText.__init__(self, *args, **kwargs)

class ArrayString(ArrayBase, BasicString):
	def __init__(self, *args, **kwargs):
		self._keykinds(kwargs)
		BasicString.__init__(self, *args, **kwargs)

def ArrayType(**kwargs):
	return (ArrayText if config.arraytext else ArrayString)(**kwargs)