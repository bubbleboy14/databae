import operator, base64, json, hashlib
from datetime import datetime
from fyg.util import log
from .config import config

modbulkers = {}
modelsubs = {}
operators = {
    "==": operator.__eq__,
    ">=": operator.__ge__,
    "<=": operator.__le__,
    "!=": operator.__ne__,
    ">": operator.__gt__,
    "<": operator.__lt__
}

def get_bulker(modelName):
    return modbulkers.get(modelName.lower(), None)

def reg_bulker(modelName, func):
    modbulkers[modelName.lower()] = func

def get_model(modelName):
    return modelsubs.get(modelName.lower(), None)

def get_iname(mod):
    if type(mod) is str:
        mod = get_model(mod)
    return getattr(mod, "indexname", "index")

def get_schema(modname=None):
    if modname:
        if not isinstance(modname, str):
            modname = modname.__name__
        return modelsubs[modname.lower()]._schema
    s = {}
    for key, val in list(modelsubs.items()):
        if key not in ["modelbase", "flatbase", "ctrefcount"]:
            s[key] = val._schema
    return s

def dprep(obj, schema=None): # prepares data object for model
    schema = schema or get_schema(obj["modelName"])
    o = {}
    for key, prop in list(schema.items()):
        if key in obj:
            if prop == "datetime" and obj[key]:
                o[key] = datetime.strptime(obj[key].replace("T", " ").replace("Z", ""), "%Y-%m-%d %X")
            if prop == "date" and obj[key]:
                o[key] = datetime.strptime(obj[key][:10], "%Y-%m-%d")
#            elif prop == "string" and isinstance(obj[key], str):
#                o[key] = obj[key].encode("utf-8")
            elif key != "_label":
                o[key] = obj[key]
    return o

def pad_key(compkey):
    if compkey[-3:-1] == "CT":
        compkey = compkey[:-3] + int(compkey[-1]) * "="
    return compkey

def unpad_key(compkey):
    val = compkey and compkey.strip("=")
    if val != compkey:
        val += "CT" + str(len(compkey) - len(val))
    return val

def ct_key(modelName, index):
    return unpad_key(base64.b64encode(json.dumps({
        "index": index,
        "model": modelName
    }).encode()).decode())

def merge_schemas(bases, label=None):
    kinds = {}
    schema = {}
    if config.flatkeysize:
        schema["key"] = "key_immutable"
    if not config.index.named: # TODO : set named indexes!
        schema["index"] = "immutable"
    for base in bases:
        if hasattr(base, "_schema"):
            schema.update(base._schema)
            kinds.update(base._schema["_kinds"])
    schema["_kinds"] = kinds
    if label:
        schema["_label"] = label
    return schema

def hashpass(password, date):
    return hashlib.md5((password + str(date.date()).replace('-','')).encode()).hexdigest()

def blobify(d, blobifier, extant=None):
    import requests
    for key, prop in list(get_schema(d["modelName"]).items()):
        if prop == "blob" and d[key]:
            entkey = d.get("gaekey", d["key"])
            if extant and getattr(extant, key): # skip if some blob is present.........
                log("%s.%s: already blobbed"%(d["modelName"], key))
                del d[key]
            else:
                log("fetching %s.%s (%s.%s)"%(d["modelName"], key, entkey, d[key]))
                d[key] = requests.get(blobifier%(entkey, key)).content