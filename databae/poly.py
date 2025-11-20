from .model import ModelCore, PolyMeta, Integer, String, CompositeKey, DateTime

class ModelBase(ModelCore, metaclass=PolyMeta):
    index = Integer(primary_key=True)
    polytype = String()
    key = CompositeKey()
    __mapper_args__ = {
        "polymorphic_on": polytype,
        "polymorphic_identity": "modelbase",
        "with_polymorphic": "*"
    }

class TimeStampedBase(ModelBase):
    created = DateTime(auto_now_add=True)
    modified = DateTime(auto_now=True)