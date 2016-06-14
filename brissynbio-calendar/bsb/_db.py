# -*- coding: utf-8 -*-

from bsb import *
from google.appengine.ext import ndb
from google.appengine.api import memcache

import pickle

def setFromInfo(dbobj, info):
    dbobj.key = info._getKey()
    dbobj.name = info.name
    dbobj.information = info.information

def _get_items(CLASS_INFO, CLASS, registry):
    if registry:
        items = CLASS.getQuery(registry).fetch()
    else:
        items = CLASS.getQuery().fetch()

    infos = []
    for item in items:
        infos.append( CLASS_INFO(item) )

    return infos

def getAllFromDB(account, CLASS, registry):
    """Function to download a dictionary of the entire contents of this database"""
    if registry:
        items = CLASS.getQuery(registry).fetch()
    else:
        items = CLASS.getQuery().fetch()

    if not items:
        return {}

    keys = list(items[0].to_dict().keys())
    keys.sort()

    output = []
    output.append(keys)

    for item in items:
        data = item.to_dict()
        line = []
        for key in keys:
            line.append(data[key])
        output.append(line)

    return output

def deleteDB(account, CLASS_INFO, CLASS, registry=None):
    """Function used to completely delete the entire database for class 'CLASS'
       contained in the registry 'registry'"""

    assert_is_admin(account, "Only administrator accounts can delete a database!")

    if registry:
        items = CLASS.getQuery(registry).fetch()
    else:
        items = CLASS.getQuery().fetch()

    keys = []

    for item in items:
        keys.append( item.key )

    ndb.delete_multi( keys )

def backup(account, CLASS_INFO, CLASS, registry=None):
    """Function used to return a string containing the entire database for class 'CLASS'
       backed up from the passed registry"""

    assert_is_admin(account, "Only administrator accounts can backup and restore the database.")
    return pickle.dumps( _get_items(CLASS_INFO, CLASS, registry) )

def restore(account, CLASS_INFO, CLASS, data, registry=None, delete_existing=True):
    """Function to restore the database from the passed 'data' string"""

    if not data:
        # nothing to restore
        return

    assert_is_admin(account, "Only administrator accounts can backup and restore the database.")

    # load all of the items
    items = pickle.loads(data)

    bad_items = []

    for item in items:
        if item.__class__ != CLASS_INFO:
            bad_items.append( str(item) )

    if len(bad_items) > 0:
        raise InputError("Cannot restore as some of the objects are of the wrong type (should be '%s') (%s)" \
                              % (CLASS_INFO, str(bad_items)), detail=bad_items)

    # save the existing database
    existing_items = _get_items(CLASS_INFO, CLASS, registry)

    if delete_existing:
        # now delete the existing data
        deleteDB(account, CLASS_INFO, CLASS, registry)

    try:
        dbitems = []

        for item in items:
            dbitem = CLASS()
            dbitem.setFromInfo(item)
            dbitems.append(dbitem)

        ndb.put_multi(dbitems)
    except:
        # restore the original data 
        dbitems = []
   
        for item in existing_items:
            dbitem = CLASS()
            dbitem.setFromInfo(item)
            dbitems.append(dbitem)

        ndb.put_multi(dbitems)

class StandardInfo:
    """Base class of all of the standard 'Info' classes,
       for database objects that have an 'idstring', 'name' and 'information'"""
    def __init__(self, item, registry):
        self._registry = None
        self.name = None
        self.idstring = None
        self.id = None
        self.information = {}
        self._CLASS = None

        if item:
            self._registry = registry
            self.idstring = unicode(item.key.string_id())
            self.id = self.idstring

            if item.name:
                self.name = unicode(item.name)
            if item.information:
                self.information = item.information
 
            self._CLASS = item.__class__
 
    def _get_infokeys(self):
        keys = list(self.information.keys())
        keys.sort()
        return keys

    information_keys = property(_get_infokeys)

    def _getKey(self):
        """Return the key for the datastore object that contains the data for this info"""
        if not self.idstring:
            return None

        return ndb.Key(self._CLASS, self.idstring, parent=self._CLASS.ancestor(self._registry))

    def _getFromDB(self):
        """Return the underlying datastore object that contains the data for this lab"""
        if not self.idstring:
            return None

        key = self._getKey()
        item = key.get()

        if not item:
            raise DataError("""There is a bug as the data for %s '%s' seems to 
                               have disappeared from the data store!""" % (self._CLASS,self.name),
                            detail=self)

        return item

    def setInformation(self, account, info, needs_admin=True):
        """Function called to set the information about object to 'info'. This
           should be a dictionary of key-value pairs"""

        if self.idstring is None:
            return

        if needs_admin:
            assert_is_admin(account, "Only administrators can change the information about an item")
        else:
            assert_is_approved(account, "Only approved accounts can change the information about an item")

        if not dicts_equal(self.information, info):
            item = self._getFromDB()
            try:
                item.information = info
                item.put()
                self.information = info
            except Exception as e:
                raise InputError("""Cannot set the information of item '%s' to '%s'.
                                    Click below for more details.""" % (item.name, info),
                                 detail=e)

def get_idstring_to_name_db(CLASS, registry):
    """Call this function to return a dictionary that maps all of the 
       items in the database for CLASS under registry to the names of
       these items"""
    key = "%s_%s_db" % (CLASS.__name__,registry)
    d = memcache.get(key)

    if d:
        return d
    else:
        d = {}
        items = CLASS.getQuery(registry).fetch()

        for item in items:
            d[ unicode(item.key.string_id()) ] = unicode(item.name)

        memcache.set(key=key, value=d)

        return d

def get_sorted_names_to_idstring(CLASS, registry):
    k = "%s_%s_ll" % (CLASS.__name__,registry)
    d = memcache.get(k)

    if d:
        return d
    else:
        d = {}
        items = CLASS.getQuery(registry).fetch()

        for item in items:
            d[unicode(item.name)] = unicode(item.key.string_id())

        l = []

        keys = list(d.keys())
        keys.sort()

        for key in keys:
            l.append( (key,d[key]) )

        memcache.set(key=k, value=l)

        return l

def changed_idstring_to_name_db(CLASS, registry):
    """Call this function to signal that the idstring to name db has been
       changed for this CLASS and registry"""
    memcache.set( "%s_%s_db" % (CLASS.__name__,registry), None )
    memcache.set( "%s_%s_ll" % (CLASS.__name__,registry), None )

def get_db(CLASS, idstring, registry=None):
    """Return the database item matching IDString 'idstring'"""
    if not idstring:
        return None

    if registry:
        key = ndb.Key( CLASS, idstring, parent=CLASS.ancestor(registry) )
    else:
        key = ndb.Key( CLASS, idstring, parent=CLASS.ancestor() )

    item = key.get()
    return item

def get_item(CLASS, CLASS_INFO, idstring, registry):
    """Return the object matching idstring 'idstring' of type CLASS
       from the registry 'registry', returning the object converted to 
       type CLASS_INFO"""

    item = get_db(CLASS, idstring, registry)

    if item:
        return CLASS_INFO(item)
    else:
        return None

def number_of_items(CLASS, registry):
    """Return the number of items in the passed registry for the passed CLASS type"""
    return CLASS.getQuery(registry).count()

def list_items(CLASS, CLASS_INFO, registry, sorted=True):
    """Function to return a list of all entries of type CLASS in the passed registry,
       where each item is converted to an object of type CLASS_INFO"""

    items = CLASS.getQuery(registry).fetch()

    output = []

    if sorted:
        sorted_items = {}
        for item in items:
            sorted_items[item.name] = CLASS_INFO(item)

        keys = list(sorted_items.keys())
        keys.sort()

        for key in keys:
            output.append( sorted_items[key] )

    else:
        for item in items:
            output.append( CLASS_INFO(item) )

    return output
