import os
from fyg.util import rm, read, write, indir
from .types import BasicInt
from .config import config

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
			if type(data) != bytes:
				data = data.encode()
			write(data, self.path, binary=True)

	def delete(self):
		if self.value:
			rm(self.path)
			self._set_path()

	def urlsafe(self):
		return self.path and "/" + "/".join(os.path.split(self.path))

class Blob(BasicInt):
	def __init__(self, *args, **kwargs):
		self.unique = kwargs.pop("unique", False)
		BasicInt.__init__(self, *args, **kwargs)

	def process_bind_param(self, data, dialect):
		if type(data) is not BlobWrapper:
			if self.unique:
				match = indir(data, config.blob)
				if match:
					return int(match)
			data = BlobWrapper(data)
		return data.value

	def process_result_value(self, value, dialect):
		return BlobWrapper(value=value)