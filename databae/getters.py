import os, json, magic
from base64 import b64decode
from datetime import datetime
from sqlalchemy import func
from six import string_types
from .util import *
from .config import config

def _apply_filter(query, key, obj, modelName, joinz):
    from .properties import KeyWrapper
    val = obj["value"]
    comp = obj["comparator"]
    if "." in key:
        altname, key = key.split(".")
        mod = get_model(altname)
        schema = get_schema(altname)
        if altname not in joinz:
            _join(modelName, altname, joinz, query)
    else:
        schema = get_schema(modelName)
        mod = get_model(modelName)
    prop = getattr(mod, key)
    ptype = schema[key]
    if ptype == "key" and not isinstance(val, KeyWrapper):
        val = KeyWrapper(val)
    elif ptype == "datetime" and not isinstance(val, datetime):
        val = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
    if comp == "like":
        query.filter(func.lower(prop).like(val.lower()))
    elif comp == "contains":
        query.filter(prop.contains(val))
    elif comp == "lacks":
        query.filter(~prop.contains(val))
    elif comp == "mod":
        query.filter(prop % val == 0)
    elif comp.startswith("near"): # lat/lng
        mdist = 10
        if "_" in comp:
            mdist = int(comp.split("_")[1])
        rad = mdist / 69.11
        query.filter(prop > val - rad)
        query.filter(prop < val + rad)
    elif comp == "!=" and type(val) == list: # allow multiple exclusions...
        for item in val:
            query.filter(operators[comp](prop, item))
    else:
        query.filter(operators[comp](prop, val))

def _join(modelName, altname, joinz, query):
    joinz.add(altname)
    altschema = get_schema(altname)
    if modelName in altschema["_kinds"]:
        mod1 = get_model(modelName)
        mod2 = get_model(altname)
        kinds = altschema["_kinds"][modelName]
    else:
        mod1 = get_model(altname)
        mod2 = get_model(modelName)
        kinds = get_schema(modelName)["_kinds"][altname]
    for kind in kinds:
        if hasattr(mod2, kind):
            mod2attr = getattr(mod2, kind)
            break
    query.join(get_model(altname), mod1.key == mod2attr)

def get_page(modelName, limit, offset, order='index', filters={}, session=None, count=False, exporter="export"):
    query = get_model(modelName).query(session=session)
    joinz = set()
    for key, obj in list(filters.items()):
        _apply_filter(query, key, obj, modelName, joinz)
    if "." in order:
        mod, attr = order.split(".")[-2:]
        if joinz or not get_model(attr): # skip refcount shortcut if filtering on joined table
            desc = False
            if mod.startswith("-"):
                desc = True
                mod = mod[1:]
            order = getattr(get_model(mod), attr)
            if desc:
                order = -order
            mod not in joinz and _join(modelName, mod, joinz, query)
    query.order(order)
    if count:
        return query.count()
    return [getattr(d, exporter)() for d in query.fetch(limit, offset)]

def getall(entity=None, query=None, keys_only=False, session=None):
    if query:
        res = query.all()
    elif entity:
        res = entity.query(session=session).all()
    if keys_only: # TODO: query for keys. for now, do with query.
        return [r.key for r in res]
    return res

def b64d(compkey):
    return b64decode(pad_key(compkey)).decode()

def key2data(b64compkey):
    if not isinstance(b64compkey, string_types):
        b64compkey = b64compkey.urlsafe()
    return json.loads(b64d(b64compkey))

def get(b64compkey, session=None):
    try:
        compkey = key2data(b64compkey)
    except:
        from fyg.util import error
        error("bad key: %s"%(b64compkey,))
    return modelsubs[compkey["model"]].query(session=session).query.get(compkey["index"])

def get_multi(b64keys, session=None):
    # b64keys can be Key instances or b64 key strings
    if b64keys and not isinstance(b64keys[0], string_types):
        b64keys = [k.urlsafe() for k in b64keys]
    keys = [json.loads(b64d(k)) for k in b64keys]
    ents = {}
    res = {}
    for k in keys:
        mod = k["model"]
        if mod not in ents:
            ents[mod] = {
                "model": modelsubs[mod],
                "indices": []
            }
        ents[mod]["indices"].append(k["index"])
    for key, val in list(ents.items()):
        mod = val["model"]
        for r in mod.query(session=session).filter(mod.index.in_(val["indices"])).all():
            res[r.id()] = r
    return [res[k] for k in b64keys]

def get_blobs(variety):
    bp = config.blob
    bz = []
    for f in next(os.walk(bp))[-1]:
        fp = os.path.join(bp, f)
        if variety in magic.from_file(fp):
            bz.append("/%s"%(fp,))
    return bz