# -*- coding: utf-8 -*-

from apiclient.discovery import build
from apiclient import errors

from oauth2client import client
from oauth2client.anyjson import simplejson
from oauth2client.appengine import StorageByKeyName
from oauth2client.appengine import CredentialsProperty

from google.appengine.ext import ndb
from google.appengine.ext import db
from google.appengine.api import users

import httplib2
import cgi
import os
import time
import re
import datetime
import pprint

import bsb._db as _db

from bsb import *

# Credentials model to store credentials in the datastore
class CredentialsModel(db.Model):
  credentials = CredentialsProperty()

def isLocal():
    return os.environ["SERVER_NAME"] in ("localhost", "www.lexample.com")

# The expected email address for the calendar account
calendar_email = "brissynbio.equipment@gmail.com"

def getFlow(session_key=None):
    """Return the flow object used for authenticating access to the calendar.
       This is hidden behind a function to delay reading the client secrets
       file for as long as possible (slows start-up)"""
 
    # flow used to authenticate the calendar user account
    if isLocal():
        flow = client.flow_from_clientsecrets(
                'client_secrets.json',
                scope='https://www.googleapis.com/auth/calendar',
                redirect_uri='http://localhost:8080/calendar/oauth2callback')
    else:
        flow = client.flow_from_clientsecrets(
            'client_secrets.json',
            scope='https://www.googleapis.com/auth/calendar',
            redirect_uri='http://starry-iris-830.appspot.com/calendar/oauth2callback')
    
    # ensure that we validate for offline use (so that we get a refresh token
    flow.params['access_type'] = 'offline'
  
    # ensure that we prompt the user to re-validate. Without this, we won't
    # get a refresh token on the second approval
    flow.params['approval_prompt'] = 'force'
    # push the user to use the calendar account
    flow.params['login_hint'] = calendar_email

    if session_key:
        # state parameter that can check that we have not been intercepted - need to save into the session
        flow.params['state'] = session_key # ''.join(random.choice(string.ascii_uppercase + string.digits)
                                           #                  for x in xrange(32))
    return flow


class CalendarError(SchedulerError):
    pass

class ConnectionError(CalendarError):
    pass

class MissingCalendarAccountError(CalendarError):
    pass

class InvalidUserError(CalendarError):
    pass

class InvalidEventError(CalendarError):
    pass

class InvalidCredentialsError(CalendarError):
    pass

class MissingCalendarError(CalendarError):
    pass

class DuplicateCalendarError(CalendarError):
    pass

calendar_account = "bsb.calendar.account"


def calendarPrefix():
    """Return the prefix attached to all created calendars. This is used
       to separate debugging calendars from production calendars"""
    if isLocal():
        return "debug.bsb"
    else:
        return "BSB"

def calendarDescription():
    """A string added to the calendar description to identify the 
       calendar as having been created and managed by this account"""
    if isLocal():
        return "BrisSynBio[DEBUG] equipment scheduler managed calendar"
    else:
        return "BrisSynBio equipment scheduler managed calendar"

def calendarName(name):
    """Return the full name for the calendar called 'name'"""
    return "%s.%s" % (calendarPrefix(),name)

def assertAdminAccount(account, message):
    """Function that asserts that the passed account is a valid account with admin privilages"""
    if account is None or not account.is_approved or not account.is_admin:
        raise InvalidUserError(message)

def assertValidAccount(account, message):
    """Function that asserts that the passed account is a valid account that has been approved"""
    if account is None or not account.is_approved:
        raise InvalidUserError(message)

def disconnectCalendarAccount(account):
    """Function called to disconnect the calendar account (delete the credentials)
       You can only do this if you are an admin user"""
    assertAdminAccount(account, "Only admin accounts are allowed to disconnect the calendar account!")

    storage = StorageByKeyName(CredentialsModel, calendar_account, 'credentials')
    credentials = storage.get()

    if credentials:
        # create an http object to ask to revoke the credentials
        storage.delete()
        http = httplib2.Http()
        credentials.revoke(http)

def setCalendarAccount(account, auth_code, session_key=None):
    """Function used to login to and save the credentials for the 
       central calendar account using the authorization code 'auth_code'. 
       This only needs to be done once,
       and you can only do this if you are an admin user."""
    
    assertAdminAccount(account, "Only admin accounts are allowed to set the calendar account!")

    storage = StorageByKeyName(CredentialsModel, calendar_account, 'credentials')
    credentials = storage.get()

    if credentials:
        if credentials.invalid:
            raise InvalidCredentialsError("Your credentials have become invalid! (probably expired)")
        else:
            raise InvalidCredentialsError("You cannot set the credentials as they already exist. Delete them first!")

    credentials = getFlow(session_key).step2_exchange(auth_code)

    if credentials is None:
       raise InvalidCredentialsError("Cannot gain the necessary credentials from the passed authorization code")

    storage.put(credentials)

def disconnectCalendarAccountURL():
    """Return the URL to call if you want to disconnect the calendar account"""
    return "/calendar/disconnect_account"

def connectCalendarAccountURL(session_key=None):
    """Return the URL to call if you want to connect the calendar account"""
    return getFlow(session_key).step1_get_authorize_url()

def hasCalendarAccount():
    storage = StorageByKeyName(CredentialsModel, calendar_account, 'credentials')
    credentials = storage.get()

    if credentials is None:
        return False
    elif credentials.access_token_expired:
        return True
    elif credentials.invalid:
        return False
    else:
        return True

def _getCalendarService():
    """Internal function that gets the calendar service account without
       checking if the user account is valid."""
    storage = StorageByKeyName(CredentialsModel, calendar_account, 'credentials')
    credentials = storage.get()

    if credentials is None:
        raise MissingCalendarAccountError()

    # create an http object, authenticate it
    http = httplib2.Http()

    if credentials.access_token_expired:
        # POSSIBLE RACE CONDITION - TWO PEOPLE MAY SIMULTANEOUSLY REFRESH
        # THIS ACCESS TOKEN!
        # the access token has expired - use the refresh token to get a new access token
        credentials.refresh(http)

        if credentials.access_token_expired:
            raise InvalidCredentialsError(
               """Cannot connect to the calendar service as have been unable to refresh the credentials.
                  Please contact an administrator for more help.""")

        # save the refreshed token
        storage.put(credentials)

    if credentials.invalid:
        raise InvalidCredentialsError("Cannot get the calendar service as the credentials are invalid!")

    http = credentials.authorize(http)

    # build a calendar service using this authentication
    service = build(serviceName="calendar", version="v3", http=http)

    return service

def getCalendarService(account):
    """Function used to return an authenticated calendar service object. 
       You must pass in a valid user account"""

    if account is None or not account.is_approved:
        raise InvalidUserError()

    return _getCalendarService()

def service_call(func, max_repeat=5):
    """Wrapper that wraps a function containing a google api service
       call, handling the errors that may occur. Note that this may
       attempt to run 'func' several times, e.g. to re-run the 
       service call if a timeout error occurred"""
    def inner(service):
        authorization_failed = False

        for n in range(0, max_repeat):
            try:
                result = func(service)
                return result
            except errors.HttpError, e:
                try:
                    error = simplejson.loads(e.content).get('error')
                except ValueError:
                    # could not load the json
                    raise ConnectionError("""Unknown error connecting to the service.
                                             HTTP status code %d:
                                             HTTP Reason: %s""" % (e.resp.status, e.resp.reason),
                                          json=e.content)

                error_code = error.get('code')

                try:
                    error_detail = error.get('errors')[0]
                except:
                    error_detail = {}

                try:
                    error_reason = error_detail.get('reason')
                except:
                    error_reason = "unknown"

                if error_code == 401:
                    # the service is no longer authorised. 
                    if authorization_failed:
                        # we've already had one failure, so won't tolerate another
                        raise InvalidCredentialsError("""Service call failed because the 
                          credentials used were invalid. The access token being used has
                          either expired or is invalid. Please contact the website admin and  
                          explain what happened to cause this error.""", json=error)
                    else:
                        # We need to try to refresh
                        # the access token for the calendar account and see if this works
                        service = _getCalendarService()

                        # loop around to try again, noting that we have already had one authorization failure
                        authorization_failed = True

                elif error_code == 403:
                    # lots of things cause a 403 error...
                    if error_reason in ['rateLimitExceeded', 'userRateLimitExceeded']:
                        # Apply exponential backoff.
                        time.sleep((2 ** n) + random.randint(0, 1000) / 1000)
                    else:
                        # Other error, re-raise.
                        raise ConnectionError("""There has been an error when trying to connect to the calendar.
                                                 The error code is %s, with reason %s.""" % (error_code, error_reason),
                                              json=error)

                elif error_code == 404 and error_reason == "notFound":
                    raise MissingCalendarError("""The requested calendar (or calendar entry) could not be found.""",
                                                json=error)
                else:
                    raise ConnectionError("""There has been an error when trying to connect to the calendar.
                                             The error code is %s, with reason %s.""" % (error_code, error_reason),
                                             json=error)

        return None

    return inner

class Event:
    """Base class of all calendar events."""
    def __init__(self, start_time=None, end_time=None, summary=None, location=None, description=None, gcal_id=None):
        self.setDuration(start_time, end_time)
        self.gcal_id = gcal_id

        if summary:
            self.summary = summary
        else:
            self.summary = "An anonymous event"

        if location:
            self.location = location
        else:
            self.location = "Unknown location"

        if description:
            self.description = description
        else:
            self.description = "Information about the event"

        # All times will be local london times
        self.timezone = get_timezone_string()

    def setDuration(self, start_time, end_time):
        """Set the duration of the event to 'start_time' to 'end_time'"""
        if not start_time:
            start_time = get_now_time()

        if not end_time:
            end_time = start_time + datetime.timedelta(0,3600,0)

        if start_time > end_time:
            tmp = end_time
            end_time = start_time
            start_time = tmp

        self.start_time = start_time
        self.end_time = end_time
        
    def setLocation(self, location):
        """Set the location of the event"""
        self.location = location

    def setSummary(self, summary):
        """Set the summary text for the event (what is seen in the calendar)"""
        self.summary = summary

    def setDescription(self, description):
        """Set the description of the event (what is seen in the detailed view)"""
        self.description = description

    def setID(self, id):
        """Set the google calendar ID for this event"""
        self.gcal_id = id

    def getID(self):
        """Return the google calendar ID of this event"""
        return self.gcal_id

    def __str__(self):
        """Return a string representation of the event"""
        return "Event( id='%s' start='%s', end='%s', summary='%s', location='%s', description='%s' )" % \
                 (self.gcal_id,self.start_time.strftime("%d:%m:%y %H-%M"), self.end_time.strftime("%d:%m:%y %H-%M"), 
                  self.summary, self.location, self.description)

    def toGoogleCalendarDict(self):
        """Return a google calendar-formatted dictionary for this event, suitable
           for adding the event via the google calendar API"""
        event = {
            'summary' : self.summary,
            'location' : self.location,
            'description' : self.description,
            'start' : {
               'dateTime' : localise_time(self.start_time).isoformat(),
               'timeZone' : self.timezone
            },
            'end' : {
               'dateTime' : localise_time(self.end_time).isoformat(),
               'timeZone' : self.timezone
            }
        }

        if self.gcal_id:
            event["id"] = self.gcal_id

        return event

    @classmethod
    def fromGoogleCalendarDict(cls, event):
        e = cls()

        e.setSummary( event.get('summary') )
        e.setLocation( event.get('location') )
        e.setDescription( event.get('description') )
        e.setID( event.get('id') )
        e.setDuration( event.get('start').get('dateTime'), 
                       event.get('end').get('dateTime') )

        return e

# The default registry of calendars
DEFAULT_CALENDAR_REGISTRY = "bsb.equipment.calendars"

def calendar_key(calendar_registry=DEFAULT_CALENDAR_REGISTRY):
    """Constructs a Datastore key for the calendar entry.
       We use the calendar name as the key"""
    return ndb.Key('Calendars', calendar_registry)

class Calendar(ndb.Model):
    """The main model for representing an individual calendar."""
    
    # name of the calendar used to identify the calendar
    name = ndb.StringProperty(indexed=True)

    # the id of the calendar in google calendars
    gcal_id = ndb.StringProperty(indexed=False)

    # list of email addresses that are allowed to view this calendar
    viewers = ndb.StringProperty(indexed=False,repeated=True)

    # information about the calendar in a dictionary
    information = ndb.JsonProperty(indexed=False)

    # whether or not modification to this calendar can only be
    # performed by admin accounts
    needs_admin = ndb.BooleanProperty(indexed=False)

    def setFromInfo(self, info):
        _db.setFromInfo(self, info)
        self.gcal_id = info.gcal_id
        self.viewers = info.viewers
        self.needs_admin = info.needs_admin

    @classmethod
    def getQuery(cls, registry=DEFAULT_CALENDAR_REGISTRY):
        return cls.query(ancestor=calendar_key(registry))

    @classmethod
    def ancestor(cls, registry=DEFAULT_CALENDAR_REGISTRY):
        return calendar_key(registry)


class CalendarInfo(_db.StandardInfo):
    """Simple class to hold the information about a calendar"""
    def __init__(self, calendar=None, registry=DEFAULT_CALENDAR_REGISTRY):
        _db.StandardInfo.__init__(self, calendar, registry)

        self.name = "unknown"
        self.gcal_id = None
        self.needs_admin = False
        self.viewers = []

        if calendar:
            if calendar.name:
                self.name = unicode(calendar.name)
            if calendar.gcal_id:
                self.gcal_id = unicode(calendar.gcal_id)

            for viewer in calendar.viewers:
                self.viewers.append( unicode(viewer) )

            self.needs_admin = calendar.needs_admin

    @classmethod
    def getAll(cls, account, registry=None):
        """Return all of the items in the database"""
        return _db.getAllFromDB(account, Calendar, registry)

    @classmethod
    def backup(cls, account, registry=None):
        """Return a string containing the entire database in pickled form"""
        return _db.backup(account, cls, Calendar, registry)

    @classmethod
    def restore(cls, account, data, registry=None):
        """Restore the database from the passed 'data' string containing a pickle of all of the objects"""
        _db.restore(account, cls, Calendar, data, registry)

    @classmethod
    def deleteDB(cls, account, registry=None):
        """Delete the entire database"""
        _db.deleteDB(account, cls, Calendar, registry)

    def _forceCreateGCal(self, service, calendar_info):
        """Internal function to create a calendar on google calendar and return the google calendar ID"""

        # first see if there are any existing calendars with this information. If there are,
        # then return a reference to this calendar, rather than creating a new calendar
        @service_call
        def get_matching_calendar(service):
            page_token = None
            output = []
            while True:
                calendars = service.calendarList().list(pageToken=page_token,
                                                        minAccessRole="owner",
                                                        showHidden=True).execute()
                for calendar in calendars['items']:
                    same_calendar=True

                    output.append("=== %s ===" % calendar["summary"])
                    output.append("=== %s ===" % calendar["id"])

                    for key in calendar_info:
                        if key in calendar:
                            if calendar_info[key] != calendar[key]:
                                same_calendar = False
                                break
                        else:
                            same_calendar = False
                            break

                    if same_calendar:
                        return calendar["id"]
                                        
                page_token = calendars.get('nextPageToken')
                if not page_token:
                    break

            return None

        matching_calendar = get_matching_calendar(service)

        if matching_calendar:
            return matching_calendar

        @service_call
        def call_service(service):
            cal = service.calendars().insert(body=calendar_info).execute()
            return cal

        cal = call_service(service)

        if cal:
            return cal['id']
        else:
            return cal

    def _forceDeleteGCal(self, service, gcal_id):
        """Internal function used to actually delete the calendar with gcal_id
           from google calendar"""

        if not service:
            return

        if not gcal_id:
            return

        @service_call
        def call_service(service):
            service.calendars().delete(calendarId=gcal_id).execute()
            return

        call_service(service)

    def _forceAddViewers(self, service, emails):
        """Internal function used to actually add the passed email addesses as viewers of this calendar"""
        if len(emails) == 0:
            return

        @service_call
        def call_service( args ):
            service = args[0]
            email_address = args[1]

            rule = {
                'scope' : {
                          'type': 'user',
                          'value': email_address,
                 },
                 'role' : 'reader'
            }

            created_rule = service.acl().insert(calendarId=self.gcal_id, body=rule).execute()

            return created_rule

        created_rules = []
        for email in emails:
            created_rule = call_service( (service, email) )
            created_rules.append(created_rule)

        return created_rules

    def _getACLs(self, service):
        """Function used to return a list of all the acls (access controls) for this calendar"""
        if not self.gcal_id:
            return None

        @service_call
        def call_service(service):
            output = []

            acls = service.acl().list(calendarId=self.gcal_id).execute()
            for acl in acls['items']:
                output.append(acl)

            return output

        acls = call_service(service)

        return acls

    def _forceSetViewers(self, service, emails):
        """Internal function used to set the list of viewers to the passed list of emails"""

        # first, get the list of current ACLs
        acls = self._getACLs(service)

        existing = []
        to_remove = []
        to_add = []

        for acl in acls:
            if acl["role"] != "owner":
                if acl["scope"]["type"] == "user":
                    email = to_email( acl["scope"]["value"] )
                    existing.append(email)

                    if not (email in emails):
                        to_remove.append(acl)

        if not emails:
            emails = []

        for email in emails:
            if not (email in existing):
                to_add.append(email)

        # add everyone that needs adding...
        if len(to_add) > 0:
            self._forceAddViewers(service, to_add)

        if len(to_remove) > 0:
            @service_call
            def call_service( args ):
                service = args[0] 
                acl = args[1]
                rule_id = acl["id"]
                service.acl().delete(calendarId=self.gcal_id, ruleId=rule_id).execute()

            for acl in to_remove:
                call_service( (service,acl) )        

    def _createCalendar(self, service):
        """Internal function used to actually create the calendar in google calendar, 
           returning the google calendar ID of the calendar. This will always create
           a new calendar"""

        if self.name is None:
            return None

        if self.gcal_id:
            # we already have a gcal_id of a calendar. We cannot create another one without deleting the first
            raise DuplicateCalendarError("""You cannot create the calendar for '%s' as it already has a valid google calendar
                                            with gcal_id = '%s'""" % (self.name, self.gcal_id), details=self)

        calendar_info = { 'summary' : cgi.escape(calendarName(self.name)),
                          'description' : cgi.escape(calendarDescription()),
                          'timeZone' :  "Europe/London" }

        cal = self._forceCreateGCal(service, calendar_info)

        calendar = self._getFromDB()

        if not calendar.gcal_id:
            calendar.gcal_id = cal
            calendar.put()
            self.gcal_id = cal

            # now ensure that all of the viewers are added
            self._forceSetViewers(service, self.viewers)
        else:
            # someone else has beat us to creating the calendar
            self.gcal_id = calendar.gcal_id
            self._forceDeleteGCal(service, cal)

    def _connectGCal(self, service):
        """Internal function used to ensure that there is a real google calendar
           that is sitting behind this real calendar"""

        if not service:
            return

        if not self.gcal_id:
            # we don't yet have a valid google calendar
            self._createCalendar(service)
            return

        @service_call
        def call_service(service):
            cal = service.calendars().get(calendarId=self.gcal_id).execute()
            return cal

        try:
            cal = call_service(service)
        except MissingCalendarError, e:
            # could not find the calendar, so we have to create it now
            cal = None

        if not cal:
            # the calendar doesn't exist on google calendars. We will create the
            # calendar as we always want to ensure that there is a valid google
            # calendar behind each calendar in the database
            calendar = self._getFromDB()

            cal_id = _createCalendar(service, name)

            if cal_id:
                calendar.gcal_id = cal_id
                calendar.put()
                self.gcal_id = cal_id

    def connect(self, account, service=None):
        """Function to ensure that this calendar is connected to google calendar"""
        assert_is_admin(account, "Only admin accounts can force the connection of a calendar.")

        if not service:
            service = getCalendarService(account)

        self._connectGCal(service)

    def disconnect(self, account, service=None):
        """Function to disconnect this calendar from google. Note that this will completely
           delete this calendar from google, with no backup possible"""
        assert_is_admin(account, "Only admin accounts can force the disconnection of a calendar.")

        if not self.gcal_id:
            return

        if not service:
            service = getCalendarService(account)

        #self._forceDeleteGCal(service, self.gcal_id)

        calendar = self._getFromDB()
        calendar.gcal_id = None
        calendar.put()
        self.gcal_id = None

    def assertValidAccount(self, account):
        """Call this function to assert that the passed account is allowed to do things with this calendar"""
        if self.needs_admin:
            assertAdminAccount(account, "Calendar '%s' can only be accessed by an administration account" \
                                            % self.name)
        else:
            assertValidAccount(account, "Calendar '%s' can only be accessed by an approved user account" \
                                            % self.name)

    def listEvents(self, account, service=None):
        """Function used to return a list of all of the events in this calendar"""
        if not self.gcal_id:
            return None

        self.assertValidAccount(account)

        if not service:
            service = getCalendarService(account)

        @service_call
        def call_service(service):
            page_token = None
            output = []

            while True:
                events = service.events().list(calendarId=self.gcal_id, pageToken=page_token).execute()
                for event in events['items']:
                    output.append( Event.fromGoogleCalendarDict(event) )

                page_token = events.get('nextPageToken')
                if not page_token:
                    break

            return output

        events = call_service(service)

        return events

    def removeEvent(self, account, event, service=None):
        """Removes the event 'event' from the google calendar."""
        if not event:
            return

        if not event.gcal_id:
            return

        self.assertValidAccount(account)

        if not service:
            service = getCalendarService(account)

        @service_call
        def call_service(service):
            service.events().delete(calendarId=self.gcal_id, eventId=event.gcal_id).execute()

        call_service(service)

        return

    def addEvent(self, account, event, service=None):
        """Creates the event 'event' and adds it to this calendar. Returns the event once it has been created"""
        if not event:
            return None

        self.assertValidAccount(account)

        if not service:
            service = getCalendarService(account)

        if not self.gcal_id:
            self._createCalendar(service)

        if not self.gcal_id:
            # something went wrong
            return None

        @service_call
        def call_service(service):
            e = service.events().insert(calendarId=self.gcal_id, body=event.toGoogleCalendarDict()).execute()
            return e

        e = call_service(service)

        return Event.fromGoogleCalendarDict(e)

    def updateEvent(self, account, event, service=None):
        """Update the passed event on the calendar to match 'event'"""
        if not event:
            return None

        if not event.gcal_id:
            #this event is not in the calendar - add it
            return self.addEvent(account, event, service)

        self.assertValidAccount(account)

        if not service:
            service = getCalendarService(account)

        @service_call
        def call_service(service):
            try:
                e = service.events().update(calendarId=self.gcal_id, eventId=event.gcal_id,
                                            body=event.toGoogleCalendarDict()).execute()
            except:
                e = service.events().insert(calendarId=self.gcal_id, body=event.toGoogleCalendarDict()).execute()

            return e

        e = call_service(service)

        return Event.fromGoogleCalendarDict(e)

    def getEvent(self, account, event_id, service=None):
        """Return the event matching the google calendar ID 'event_id'"""
        self.assertValidAccount(account)

        event_id = to_string(event_id)

        if not event_id:
            return None

        if not self.gcal_id:
            return None

        if not service:
            service = getCalendarService(account)

        @service_call
        def call_service(service):
            e = service.events().list(calendarId=self.gcal_id, eventId=event_id).execute()
            return e

        e = call_service(service)

        return Event.fromGoogleCalendarDict(e)

    def addViewer(self, account, email_address, service=None):
        """Function used to add the passed email address as a viewer to the
           ACL list of this calendar"""
        self.assertValidAccount(account)

        email_address = to_email(email_address)

        if not email_address:
            return None

        if email_address.endswith("@example.com"):
            return

        if email_address in self.viewers:
            # already added as a viewer
            return

        if self.gcal_id:
            if not service:
                service = getCalendarService(account)

            # add the viewer now
            self._forceAddViewers(service, [email_address])

        calendar = self._getFromDB()
        calendar.viewers.append(email_address)
        calendar.put()

        self.viewers.append(email_address)

    def setViewers(self, account, viewers, service=None):
        """Function used to set the passed list of email addresses as valid viewers of this calendar"""
        self.assertValidAccount(account)

        cleaned = []

        if not viewers:
            viewers = []

        for viewer in viewers:
            viewer = to_email(viewer)

            if not viewer.endswith("@example.com"):
                if not viewer in cleaned:
                    cleaned.append(viewer)

        # now see if this changes anything
        if len(cleaned) == len(self.viewers):
            no_change = True

            for viewer in self.viewers:
                if not (viewer in cleaned):
                    no_change = False
                    break

            if no_change:
                # nothing has changed - nothing to do
                return

        if self.gcal_id:
            if not service:
                service = getCalendarService(account)

            # set the viewers now
            self._forceSetViewers(service, cleaned)

        calendar = self._getFromDB()
        calendar.viewers = cleaned
        calendar.put()

        self.viewers = cleaned

    def getURL(self, account, show_title=True, mode="WEEK"):
        """Function to return a link to the web page for this calendar"""
        self.assertValidAccount(account)

        if not self.gcal_id:
            return "/calendar/not_connected?calendar=%s" % self.idstring

        #elif account.email.endswith("@example.com") or account.email in self.viewers:
        else:
            return "https://www.google.com/calendar/embed?" \
                          "showTitle=&amp;"  \
                          "showPrint=0&amp;"  \
                          "showCalendars=0&amp;" \
                          "showTz=0&amp;" \
                          "mode=%s&amp;" \
                          "wkst=2&amp;" \
                          "hl=en_GB&amp;" \
                          "src=%s" % (mode, re.sub('@', '%40', self.gcal_id))

        #else:
        #    return "/calendar/not_visible?calendar=%s" % self.idstring

    def getEmbedHTML(self, account, width="100%", height="600", calendar_type="week"):
        """Function to return the html needed to embed this calendar
           into the current page"""
        self.assertValidAccount(account)

        mode = "WEEK"

        if calendar_type == "month":
            mode = "MONTH"

        if not self.gcal_id:
            if account.is_admin:
                self.connect(account)
                if self.gcal_id:
                    return self.getEmbedHTML(account, width, height)

            return """<p>The calendar '%s' has not yet been connected to Google.
                         Please <a href="mailto:brissynbio-equipment@bristol.ac.uk">email us</a>, 
                         letting us know of this problem.</p>""" % (self.name)

        #elif (account.email in self.viewers) or (account.email.endswith("@example.com")):
        else:
            return "<iframe src=\"%s\" style=\" border-width:0 \" " \
                                  "width=\"%s\" height=\"%s\" " \
                                  "frameborder=\"0\" scrolling=\"no\"></iframe>" % \
                                       (self.getURL(account,show_title=False,mode=mode), width, height)
        #else:
        #    return "<p>Your account (%s) does not have permission to view the calendar '%s'.</p>" % \
        #             (account.email, self.name)

def list_calendars(sorted=True, calendar_registry=DEFAULT_CALENDAR_REGISTRY):
    """Function to return the list of calendars available to this system"""
    return _db.list_items(Calendar, CalendarInfo, calendar_registry, sorted)

def number_of_calendars(calendar_registry=DEFAULT_CALENDAR_REGISTRY):
    """Function to return the total number of calendars"""
    return _db.number_of_items(Calendar, calendar_registry)

def get_calendar(account, idstring, calendar_registry=DEFAULT_CALENDAR_REGISTRY):
    """Function used to return the CalendarInfo object for the calendar with matching IDString"""
    assertValidAccount(account, """You must have a valid, approved account to get access to 
                                   the calendar with ID '%s'""" % idstring)

    calendar = _db.get_item(Calendar, CalendarInfo, idstring, calendar_registry)    

    if calendar:
        if calendar.needs_admin:
            assertAdminAccount(account, """You must have a valid administrator's account to get access to 
                                           the calendar with name '%s'""" % calendar.name)

    return calendar

def get_calendar_by_name(account, name, calendar_registry=DEFAULT_CALENDAR_REGISTRY):
    """Function to return a CalendarInfo object for the calendar with name 'name'"""
    name = to_string(name)
    return get_calendar(account, name_to_idstring(name), calendar_registry)

def add_calendar(account, name, needs_admin=False,
                 calendar_registry=DEFAULT_CALENDAR_REGISTRY):
    """Function used to create a new calendar called 'name'. Note that your account
       must have 'admin' privilages to create a new account. This returns the handle
       to the created calendar"""

    assertAdminAccount(account, "Only administration accounts are allowed to create new calendars")

    name = to_string(name)

    if not name:
        return None

    # get the IDString for this calendar
    idstring = name_to_idstring(name)

    # first, see look up the name of the calendar in the database
    calendar = _db.get_db(Calendar, idstring, calendar_registry)

    if calendar:
        # we already think that the calendar exists...
        raise DuplicateCalendarError( """You cannot create the calendar '%s' as it
                                         already appears to exist (%s).""" % (name, calendar.name) )

    info = {}
    info["name"] = name
    info["idstring"] = idstring
    info["needs_admin"] = needs_admin

    # add the calendar item
    try:
        calendar = Calendar( parent = calendar_key(calendar_registry),
                             id = idstring,
                             name = name,
                             needs_admin = needs_admin )
        calendar.put()

    except Exception as e:
        raise InputError("""Problem adding the calendar to the database! Please check the detailed
                            error message.""", detail=info, json=e)

    return CalendarInfo(calendar, calendar_registry)

def delete_calendar(account, idstring, registry=DEFAULT_CALENDAR_REGISTRY):
    """Function used to delete a calendar from the system"""
    assert_is_admin(account, "Only administrators can delete calendars from the system!")

    if not idstring:
        return

    item = _db.get_db(Calendar, idstring, registry)

    if item:
        if item.gcal_id:
            # we should do something about missing google calendars...
            CalendarInfo(item).disconnect(account)

        item.key.delete()
