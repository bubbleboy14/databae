from .types import BasicString, BasicUnsignedBig
from .getters import get
from .config import config

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

class IndexKey(BasicUnsignedBig):
	cache_ok = config.cache

	def __init__(self, *args, **kwargs):
		self.kind = kwargs.pop("kind")
		if not isinstance(self.kind, str):
			self.kind = self.kind.__name__.lower()
		BasicUnsignedBig.__init__(self, *args, **kwargs)

	def process_bind_param(self, value, dialect):
		return value

	def process_result_value(self, value, dialect):
		return KeyWrapper(value, self.kind)