# -*- coding: utf-8 -*-

import re
import pprint
import cgi
import datetime

# set up the UTC timezone - note that I am following the google 'convention' that
# any time without a timezone is actually UTC (since ndb.DateTimeProperty can't support
# timezones)
class UTC_TZ(datetime.tzinfo):
        def utcoffset(self, dt):
            return datetime.timedelta(0)
        def dst(self, dt):
            return datetime.timedelta(0)
        def tzname(self,dt):
            return "UTC"

# set up the GMT timezone
class GMT_TZ(datetime.tzinfo):
        def utcoffset(self, dt):
            return self.dst(dt)
        def dst(self, dt):
            # DST starts last Sunday in March
            d = datetime.datetime(dt.year, 4, 1)   # ends last Sunday in October
            self.dston = d - datetime.timedelta(days=d.weekday() + 1)
            d = datetime.datetime(dt.year, 11, 1)
            self.dstoff = d - datetime.timedelta(days=d.weekday() + 1)
            if self.dston <=  dt.replace(tzinfo=None) < self.dstoff:
                return datetime.timedelta(hours=1)
            else:
                return datetime.timedelta(0)
        def tzname(self,dt):
             return "GMT"

def get_now_time(no_timezone=True):
    """Function to return the current UTC date and time"""
    if no_timezone:
        return datetime.datetime.utcnow()
    else:
        return datetime.datetime.utcnow().replace(tzinfo=UTC_TZ())

def localise_time(t):
    """Return the passed UTC time localised into the current timezone.
       This will sort out any daylight saving time"""
    if t.tzinfo is None:
        return t.replace(tzinfo=UTC_TZ()).astimezone(GMT_TZ())
    else:
        return t.astimezone(GMT_TZ())

def make_plural(singular, plural, value):
    if value == 1:
        return singular
    else:
        return plural

def mins_to_string(minutes):
    """Return the passed time in minutes converted to a usable human readable string"""
    minutes = int(minutes)

    if minutes < 60:
        return "%d %s" % (minutes, make_plural("minute", "minutes", minutes))
    else:
        hours = minutes / 60
        minutes = minutes - (60*hours)

        if hours < 24:
            if minutes == 0:
                return "%d %s" % (hours, make_plural("hour", "hours", hours))
            else:
                return "%d %s and %d %s" % (hours, make_plural("hour","hours",hours),
                                            minutes, make_plural("minute","minutes",minutes))
        else:
            days = hours / 24
            hours = hours - (24*days)

            if hours == 0:
                if minutes == 0:
                    return "%d %s" % (days, make_plural("day", "days", days))
                else:
                    return "%d %s and %d %s" % (days, make_plural("day", "days", days),
                                                minutes, make_plural("minute", "minutes", minutes))
            else:
                if minutes == 0:
                    return "%d %s and %d %s" % (days, make_plural("day", "days", days),
                                                hours, make_plural("hour", "hours", hours))
                else:
                    return "%d %s, %d %s and %d %s" % (days, make_plural("day", "days", days),
                                                       hours, make_plural("hour", "hours", hours),
                                                       minutes, make_plural("minute", "minutes", minutes))

def to_utc(t, no_timezone=True):
    """Return the passed time converted to UTC"""
    if t.tzinfo is None:
        return t
    elif no_timezone:
        return t.astimezone(UTC_TZ()).replace(tzinfo=None)
    else:
        return t.astimezone(UTC_TZ())

def get_timezone_string():
    """Return the string giving data about the timezone"""
    return "Europe/London"

def get_local_now_time():
    """Return the current time already localised into the timezone of the calendar"""
    return localise_time( get_now_time(no_timezone=False) )

def get_day_from(t, get_localised_day=True):
    """Return the datetime that marks the beginning of the day of datetime 't'.
       Note that this converts the time into a localised time to work out which
       day to use, but will return a UTC timezoned day"""
    t = to_utc(t)
    return datetime.datetime(t.year, t.month, t.day, tzinfo=t.tzinfo)

from google.appengine.ext import db

class SchedulerError(Exception):
    def __init__(self, message=None, detail=None, json=None):
        Exception.__init__(self, message)
        self.error_message = message
        if detail:
            self.detail = detail

        if json:
            self.json = pprint.pformat(json)

    def errorMessage(self):
        return self.error_message

class IncompleteCodeError(SchedulerError):
    pass

class PermissionError(SchedulerError):
    pass

class InputError(SchedulerError):
    pass

class InvalidIDError(SchedulerError):
    pass

class DataError(SchedulerError):
    pass

class ProgramBug(SchedulerError):
    pass

def assert_is_admin(account, message, details=None):
    if not (account.is_approved and account.is_admin):
        raise PermissionError(message, details)

def assert_is_approved(account, message, details=None):
    if not account.is_approved:
        raise PermissionError(message, details)

def assert_is_admin_or_user(account, user, message, details=None):
    if not (account.is_approved and (account.is_admin or account.email == user)):
        raise PermissionError(message, details)

def fromDaysHoursMinutes(t, text=None):
    """Return the passed time in format Xd Xh Xm to a time in minutes. If
       the string equals 'text' then "None" is returned"""
    t = to_string(t)

    if not t:
        return None

    t = t.lower().replace(",","") \
                 .replace("minutes", "m") \
                 .replace("minute", "m") \
                 .replace("mins", "m") \
                 .replace("min", "m") \
                 .replace("hours", "h") \
                 .replace("hour", "h") \
                 .replace("days", "d") \
                 .replace("day", "d")

    if text:
        if t == text.lower():
            return None

    m = re.search(r"(\s*[\d\.]+\s*[h,m,d]){0,1}(\s*[\d\.]+\s*[h,m,d]){0,1}(\s*[\d\.]+\s*[h,m,d]){0,1}", t)

    if m:
        mins = 0

        for g in m.groups():
            if g:
                g = g.lstrip().rstrip().replace(" ","")

                if "m" in g:
                    mins += float( g.replace("m","") )
                elif "h" in g:
                    mins += 60 * float( g.replace("h","") )
                elif "d" in g:
                    mins += (24*60) * float( g.replace("d","") )

    return int(mins)

def to_bool(text):
    if not text:
        return False
    elif unicode(text).lower() in ["on", "yes", "1", "y", "true"]:
        return True
    else:
        return False

def to_string(text):
    try:
        return to_string( text.strftime("%d:%m:%y %H-%M") )
    except:
        if not text or text == "None":
            return None
        else:
            text = cgi.escape(unicode(text)).lstrip().rstrip()
            if len(text) == 0:
               return None
            else:
               return text

def to_int(text):
    text = to_string(text)

    if not text:
        return None

    try:
        return int(text)
    except:
        raise InputError("You have entered '%s'. This is not an integer (whole number)!" % text)

def to_number(text):
    text = to_string(text)

    if not text:
        return None
    else:
        return float(text)

def to_date(text):
    text = to_string(text)

    if not text:
        return None
    else:
        try:
            date = text.split("-")
            return datetime.datetime(int(date[2]), int(date[1]), int(date[0]), tzinfo=None)
        except Exception as e:
            raise InputError("""Cannot recognise a date from the passed string '%s'. This
                                string should have the format 'DD-MM-YYYY', e.g. '28-03-2015'""" % \
                                    text, detail=e )

def to_time(text):
    text = to_string(text)

    if not text:
        return None
    else:
        try:
            time = text.split(":")

            # assume all strings passed by the user are in GMT time
            return datetime.time(int(time[0]), int(time[1]), tzinfo=None)
        except Exception as e:
             raise InputError("""Cannot recognise a time from the passed string '%s'. This string
                                 should have the format 'HH:MM', e.g. '14:23'""" % \
                                  text, detail=e )

def to_datetime(text):
    text = to_string(text)

    if not text:
        return None
    else:
        try:
            words = text.split()
            date = None
            time = None

            date = words[0].split("-")

            try:
                time = words[1].split(":")
            except:
                time = (12,0)

            # assume all strings passed by the user are in GMT time
            return to_utc(datetime.datetime(int(date[2]), int(date[1]), int(date[0]), int(time[0]), int(time[1]),
                                            tzinfo=GMT_TZ()), no_timezone=True)
        except Exception as e:
            raise InputError("""Cannot recognise a time and date from the passed string '%s'. This
                                string should have the format 'DD-MM-YYYY HH:MM', e.g. '28-03-2015 14:23'""" % \
                                      text, detail=e )

def to_email(email):
    if not email:
        return None
    else:
        try:
            email = cgi.escape(unicode(email)).lower().replace(" ","").lstrip().rstrip()
        except Exception as e:
            raise InputError("Could not process email '%s'" % email, detail=e)

        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            #ok, looks like an email address
            return email
        else:
            return None

def to_location(text, separator=None):
    if not text:
        return None

    try:
        if separator:
            parts = text.split(separator)
        else:
            parts = text.split()

        help(db.GeoPt)

        return db.GeoPt( float(parts[0]), float(parts[1]) )
    except:
        raise InputError(
          """Could not turn '%s' into a location as it does not contain two floats. You need to
             supply the lattitude and the longitude of the location (e.g. use google 
             maps to get this)""" % str(text))
    
def to_list(text, separator=None):
    if not text:
        return []

    try:
        if separator:
            return text.split(separator)
        else:
            return text.split()
    except:
        try:
            l = []
            for item in text:
                l.append( to_string(item) )

            return l
        except:
            raise InputError("Could not turn '%s' into a list." % str(text))  
    
def to_dictionary(text, separator=","):
    if not text:
        return {}

    try:
        keys = text.keys()
        return text
    except:
        try:
            d = {}
            pairs = text.split(separator)

            for pair in pairs:
                key_value = pair.split(":")

                d[ to_string(key_value[0]) ] = to_string(key_value[1])

            return d

        except:
            raise InputError("Could not turn '%s' into a dictionary." % str(text))

def name_to_idstring(name):
    """Return the id associated with the passed name. This is 
       a lower-case version of the name with all non-alphanumeric
       characters either removed or replaced with underscores"""

    if name:
        return re.sub( r"[\s-]+", "_", re.sub(r"[^a-z\.0-9\-\s_]+", "", name.lower()))
    else:
        return None

def lists_equal(list1, list2):
    """Return if the two lists are equal"""
    if list1 == list2:
        return True

    elif len(list1) == len(list2):
        for i in range(0,len(list1)):
            if list1[i] != list2[i]:
                return False

        return True

    else:
        return False

def dicts_equal(dict1, dict2):
    """Return if two dictionaries are equal"""
    if dict1 == dict2:
        return True

    elif (not dict1) or (not dict2):
        return False

    elif not lists_equal(list(dict1.keys()), list(dict2.keys())):
        return False

    else:
        for key in dict1.keys():
            if dict1[key] != dict2[key]:
                return False

        return True

def processDictionaryEdit(page, id, sub_action):
    """Function to process the "dictionary edit" view form that can
       be added to a page. The dictionary items can be edited, added to and removed.
       This returns the modified dictionary."""

    items = []
    i = 0

    while True:
        i += 1
        key = page.request.get("%s_key_%s" % (id,i), None)
        value = page.request.get("%s_value_%s" % (id,i), None)

        if key and value:
            items.append( (cgi.escape(key).lstrip().rstrip(),cgi.escape(value).lstrip().rstrip()) )
        else:
             break

    #automatically add items, even if not requested
    key = page.request.get("%s_key_add" % (id), None)
    value = page.request.get("%s_value_add" % (id), None)

    if key and value:
        items.append( (cgi.escape(key).lstrip().rstrip(),cgi.escape(value).lstrip().rstrip()) )

    if sub_action.startswith("remove"):
        i = int( sub_action.split("_")[-1] ) - 1
        del( items[i] )

    d = {}

    for item in items:
        if len(item[0]) > 0 and len(item[1]) > 0:
            d[ item[0] ] = item[1]

    return d

def processBoolEdit(page, id):
    """Function to process the 'bool edit' view form that can be
       added to a page. This should return True or False"""
    item = page.request.get(id, False)

    if item:
        if item == "True":
            return True

    return False

def processListEdit(page, id, sub_action):
    """Function to process the "list edit" view form that can be 
       added to a page. The list items can be edited, added to and removed.
       This returns the modified list."""
    
    items = []
    i = 0

    while True:
        i += 1
        item = page.request.get("%s_%s" % (id,i), None)
        if item:
            items.append(cgi.escape(item).lstrip().rstrip())
        else:
            break

    #automatically add items, even if not requested
    item = page.request.get("%s_add" % (id), None)
    if item:   
        items.append(cgi.escape(item).lstrip().rstrip())

    if sub_action.startswith("remove"):
        i = int( sub_action.split("_")[-1] ) - 1
        del( items[i] )

    return items

def processLocationEdit(page, id, sub_action=None):
    """Function to process the "location edit" view form that can be
       added to a page. The location can be edited. This returns
       the edited location"""

    lat = page.request.get("%s_lattitude" % id, None)
    lon = page.request.get("%s_longitude" % id, None)

    if lat and lon:
        try:
            lat = float(lat)
            lon = float(lon)
            return db.GeoPt(lat, lon)
        except Exception as e:
            raise

    return None

import admin
import accounts
import calendar
import projects
import feedback
import equipment
