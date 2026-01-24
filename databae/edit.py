from datetime import date, datetime
from .util import get_model, blobify
from .properties import KeyWrapper
from .getters import get

def _trans_key(val):
    return KeyWrapper(val)

def _trans_keylist(val):
    return [KeyWrapper(v) for v in val]

def _trans_datetime(val):
    return isinstance(val, datetime) and val or datetime.strptime(val, "%Y-%m-%d %H:%M:%S")

def _trans_date(val):
    return isinstance(val, (date, datetime)) and val or datetime.strptime(val, "%Y-%m-%d")

ETRANS = {
    "key": _trans_key,
    "keylist": _trans_keylist,
    "datetime": _trans_datetime,
    "date": _trans_date
}
def add_edit_transformation(ptype, func):
    ETRANS[ptype] = func

def edit(data, session=None, blobifier=None):
    haskey = "key" in data
    extant = haskey and get(data["key"], session)
    blobifier and blobify(data, blobifier, extant)
    ent = extant or get_model(data["modelName"])()
    if haskey: # what about nokey uniqueness checks?
        editFailure = ent.beforeedit(data)
        if editFailure:
            return editFailure
    for propname, val in list(data.items()):
        if propname in ent._schema:
            if val:
                proptype = ent._schema[propname]
                if hasattr(ent, "_pre_trans_%s"%(propname,)):
                    val = getattr(ent, "_pre_trans_%s"%(propname,))(val)
                if proptype in ETRANS:
                    val = ETRANS[proptype](val)
                if hasattr(ent, "_trans_%s"%(propname,)):
                    val = getattr(ent, "_trans_%s"%(propname,))(val)
            setattr(ent, propname, val)
    if not haskey and hasattr(ent, "oncreate"):
        ent.oncreate()
    ent.put()
    return ent