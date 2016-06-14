# -*- coding: utf-8 -*-

"""Module containing all classes needed to administer 
   the BrisSynBio equipment scheduler"""

from google.appengine.ext import db

class AdminError:
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return "AdminError: %s" % self.error

class AdminOption(db.Model):
    """Value for the admin option"""
    value = db.StringProperty(required=True) 

    @classmethod
    def getOption(cls, key):
        key = db.Key.from_path("AdminOption", key)
        option = db.get(key)

        if option:
            return option.value
        else:
            return None

    @classmethod
    def deleteOption(cls, key):
        key = db.Key.from_path("AdminOption", key)
        option = db.get(key)

        if option:
            option.delete()

def get_option(key):
    """Return the value of the admin option with key 'key', 
       or None if there is no such value"""
    return AdminOption.getOption(key)

def put_option(key, value):
    """Save the value 'value' in the set of admin options
       associated with the key 'key'"""

    if key is None or value is None:
        return

    o = AdminOption(key_name=key, value=unicode(value))
    o.put()

def delete_option(key):
    """Delete the value associated with the key 'key' from the database"""
    AdminOption.deleteOption(key)

def turn_on_maintenance_mode():
    """Turn on maintenance mode"""
    put_option("maintenance", 1)

def turn_off_maintenance_mode():
    """Turn off maintenance mode"""
    delete_option("maintenance")

def set_maintenance_state(state):
    """Set the maintenance state to 'state'"""
    if state:
        turn_on_maintenance_mode()
    else:
        turn_off_maintenance_mode()

def under_maintenance():
    """Return whether or not the website is under maintenance"""
    return not (get_option("maintenance") is None)
