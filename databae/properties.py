from .util import get_iname
from .columns import *
from .config import config

def fkprop(targetClass):
	tname = targetClass if type(targetClass) is str else targetClass.__tablename__
	iname = get_iname(targetClass)
	return sqlalchemy.ForeignKey("%s.%s"%(tname, iname))

def sqlForeignKey(targetClass, **kwargs):
	return sqlalchemy.Column(sqlalchemy.Integer, fkprop(targetClass), **kwargs)

def ForeignKey(**kwargs):
	kind = kwargs.get("kind")
	if config.index.key and kind: # single-kind, non-repeating!
		return IndexForeignKey(fkprop(kind), **kwargs)
	else:
		return FlexForeignKey(**kwargs)

def Integer(**kwargs):
	if kwargs.pop("big", False):
		return Big(**kwargs)
	else:
		return Int(**kwargs)