import sqlalchemy
from .columns import *
from .config import config

def fkprop(targetClass):
	tname = targetClass if type(targetClass) is str else targetClass.__tablename__
	return sqlalchemy.ForeignKey("%s.index"%(tname,))

def sqlForeignKey(targetClass, **kwargs):
	return sqlalchemy.Column(sqlalchemy.Integer, fkprop(targetClass), **kwargs)

def ForeignKey(**kwargs):
	if config.indexkeys: # single-kind, non-repeating!
		return IndexForeignKey(fkprop(kwargs.get("kind")), **kwargs)
	else:
		return FlexForeignKey(**kwargs)

def Integer(**kwargs):
	if kwargs.pop("big", False):
		return BIGINT(**kwargs)
	else:
		return Int(**kwargs)