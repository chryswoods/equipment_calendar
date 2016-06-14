# -*- coding: utf-8 -*-

"""Module containing all classes needed to manage feedback and bug reporting"""

from google.appengine.ext import ndb
from google.appengine.api import memcache

# cgi module
import cgi

# datetime module
import datetime

# to get a traceback from an exception
import traceback

# regular expression module used to validate user account details
import re

# import the bsb module
from bsb import *
import bsb

# uses the db module, which should be kept private
import bsb._db as _db

class FeedBackError(SchedulerError):
    pass

# The default registry for exceptions
DEFAULT_BUGS_REGISTRY = "bsb.equipment.bugs"

# The default registry for feedback
DEFAULT_FEEDBACK_REGISTRY = "bsb.equipment.feedback"

def bugs_key(registry=DEFAULT_BUGS_REGISTRY):
    """Constructs a Datastore key for a bug entry."""
    return ndb.Key('Bug', registry)

def feedback_key(registry=DEFAULT_FEEDBACK_REGISTRY):
    """Constructs a Datastore key for a feedback entry"""
    return ndb.Key('Feedback', registry)

class Bug(ndb.Model):
    """The time when the bug was reported"""
    report_time = ndb.DateTimeProperty(indexed=True, auto_now_add=False, auto_now=False)

    """The class type of the exception"""
    etype = ndb.StringProperty(indexed=True)

    """The user who reported the bug"""
    email = ndb.StringProperty(indexed=True)

    """Any extra information that the user adds to the report"""
    user_info = ndb.StringProperty(indexed=False)

    """The simple description of the bug"""
    description = ndb.StringProperty(indexed=False)

    """The detailed description of the bug"""
    detail = ndb.StringProperty(indexed=False)

    """Backtrace for the bug"""
    backtrace = ndb.StringProperty(indexed=False)

    def setFromInfo(self, info):
        self.report_time = info.report_time
        self.etype = info.etype
        self.email = info.email
        self.user_info = info.user_info
        self.description = info.description
        self.detail = info.detail
        self.backtrace = info.backtrace

    def bugID(self):
        return self.key.integer_id()

    @classmethod
    def getQuery(cls, registry=DEFAULT_BUGS_REGISTRY):
        return cls.query(ancestor=bugs_key(registry))

    @classmethod
    def ancestor(cls, registry=DEFAULT_BUGS_REGISTRY):
        return bugs_key(registry)

class BugInfo:
    """Simple class to hold information about a bug"""
    def __init__(self, bug=None, bug_id=None, registry=DEFAULT_BUGS_REGISTRY):
        self.report_time = None
        self.etype = None
        self.email = None
        self.user_info = None
        self.description = None
        self.detail = None
        self.backtrace = None
        self.bug_id = None

        if bug_id:
            self.bug_id = bug_id
            self._registry = registry
            self._CLASS = Bug
            bug = self._getFromDB()

            if not bug:
                raise DataError("There is no bug available with bug ID = '%s'" % bug_id)

        if bug:
            if bug.report_time:
                self.report_time = bug.report_time

            if bug.etype:
                self.etype = unicode(bug.etype)

            if bug.email:
                self.email = unicode(bug.email)

            if bug.user_info:
                self.user_info = unicode(bug.user_info)

            if bug.description:
                self.description = unicode(bug.description)

            if bug.detail:
                self.detail = unicode(bug.detail)

            if bug.backtrace:
                self.backtrace = unicode(bug.backtrace)

            self._CLASS = Bug
            self._registry = registry
            self.bug_id = bug.bugID()

    def __str__(self):
        return "BugInfo( bug_id = %s )" % self.bug_id

    @classmethod
    def deleteBugs(cls, account, bug_ids, registry=DEFAULT_BUGS_REGISTRY):
        """Delete all of the bugs whose IDs are in 'bug_ids'"""

        assert_is_approved(account, "Only approved accounts can delete bugs!")
        
        keys = []

        if account.is_admin:
            for bug_id in bug_ids:
                try:
                    bug_id = to_int(bug_id)
                    if bug_id:
                        keys.append( ndb.Key(Bug, bug_id, parent=Bug.ancestor(registry)) )
                except:
                    pass
        else:
            for bug_id in bug_ids:
                try:
                    bug_id = to_int(bug_id)
                    key = ndb.Key(Bug, bug_id, parent=Bug.ancestor(registry))
                    bug = key.get()
                    if bug:
                        if bug.email == account.email:
                            keys.append(key)
                except:
                    pass

        if len(keys) > 0:
            ndb.delete_multi(keys)


    def deleteBug(self, account):
        """Delete this bug"""
        assert_is_admin_or_user(account, self.email, 
                                "Only admin users or the bug owner (%s) can delete the bug" % self.email)

        key = self._getKey()
            
        if key:
            key.delete()

        self.bug_id = None
        self._CLASS = None
        self._registry = None 
        self.report_time = None
        self.etype = None
        self.email = None
        self.user_info = None
        self.description = None
        self.detail = None
        self.backtrace = None
        self.bug_id = None

    def _getKey(self):
        """Return the key for the datastore object that contains the data for this info"""
        if not self.bug_id:
            return None

        return ndb.Key(self._CLASS, self.bug_id, parent=self._CLASS.ancestor(self._registry))

    def _getFromDB(self):
        """Return the underlying datastore object that contains the data for this lab"""
        if not self.bug_id:
            return None

        key = self._getKey()
        item = key.get()

        if not item:
            raise DataError("""There is a bug as the data for the bug with bug_id='%s' seems to 
                               have disappeared from the data store!""" % (self.bug_id),
                            detail=str(self))

        return item

    def setUserInfo(self, account, user_info):
       """Allow a user to set/change the user-supplied information about this bug"""
       assert_is_admin_or_user(account, self.email,
                               "Only admin users or the bug owner (%s) can add extra information about this bug" % self.email)

       if self.user_info != user_info:
           item = self._getFromDB()
           if item:
               item.user_info = user_info
               item.put()
               self.user_info = item.user_info

    @classmethod
    def createFromError(cls, account, error, backtrace, registry=DEFAULT_BUGS_REGISTRY):
        """Create a new record for the passed error"""
        if not account:
            return

        if not account.is_approved:
            return

        if not error:
            return

        bug = Bug( parent=bugs_key(registry),
                   report_time=bsb.get_now_time(no_timezone=True),
                   email=account.email )

        try:
            bug.etype = str(error.__class__.__name__)
        except:
            pass

        backtrace = to_string(backtrace)
        
        if backtrace:
            bug.backtrace = backtrace

        try:
            bug.description = error.errorMessage()
        except:
            try:
                bug.description = error.message()
            except:
                bug.description = str(error)

        lines = []

        try:
            if e.json:
                lines.append("JSON\n%s" % e.json)
        except:
            pass

        try:
            if e.detail:
                lines.append("DETAIL\n%s" % e.detail)
        except:
            pass

        if len(lines) > 0:
            bug.detail = "\n\n".join(lines)

        bug.put()

        return BugInfo(bug)

def get_bugs(account, range_start=None, range_end=None, view_user=None,
             sorted=True, reverse_sort=True, registry=DEFAULT_BUGS_REGISTRY):
    """Return all of the errors that have occurred between 'range_start'
       and 'range_end'. These will default to the beginning and end of time
       if they are not specified"""

    assert_is_approved(account, "Only approved accounts can view all of the bugs in the system!")

    view_user = to_string(view_user)

    if view_user:
        if view_user.lower() == "all":
            view_user = None

    if not account.is_admin:
        if view_user != account.email:
            raise PermissionError("You (%s) cannot view bugs submitted by user %s" % (account.email,view_user))

    double_range=False

    if range_start and range_end:
        double_range=True

        if range_start > range_end:
            tmp = range_start
            range_start = range_end
            range_end = tmp
        elif range_start == range_end:
            return None

    query = Bug.getQuery(registry)

    if view_user:
        query = query.filter(Bug.email==view_user)

    if range_start:
        query = query.filter( Bug.report_time >= range_start )
    elif range_end:
        query = query.filter( Bug.report_time < range_end )

    items = query.fetch()

    bugs = []

    if double_range:
        for item in items:
            if item.report_time <= range_end:
                bugs.append( BugInfo(item) )
    else:
        for item in items:
            bugs.append( BugInfo(item) )

    if sorted:
        bugs.sort(key=lambda x: x.report_time, reverse=reverse_sort)

    return bugs

def get_feedback(account, range_start=None, range_end=None, 
                 sorted=True, reverse_sort=True, topic_mask=None, registry=DEFAULT_FEEDBACK_REGISTRY):
    """Return all of the user feedback that has been submitted between 'range_start'
       and 'range_end'. These will default to the beginning and end of time
       if they are not specified"""

    assert_is_approved(account, "Only approved accounts can view all of the feedback in the system!")

    double_range=False

    if range_start and range_end:
        double_range=True

        if range_start > range_end:
            tmp = range_start
            range_start = range_end
            range_end = tmp
        elif range_start == range_end:
            return None

    query = FeedBack.getQuery(registry)

    if range_start:
        query = query.filter( FeedBack.last_access_time >= range_start )
    elif range_end:
        query = query.filter( FeedBack.last_access_time < range_end )

    if topic_mask:
        if topic_mask == "open":
            query = query.filter( FeedBack.is_resolved == False )
        elif topic_mask == "my":
            query = query.filter( FeedBack.email == account.email )
        elif topic_mask == "problem":
            query = query.filter( FeedBack.ftype.IN( problem_ftypes ) ).filter( FeedBack.is_resolved == False )
        elif topic_mask == "help":
            query = query.filter( FeedBack.ftype.IN( help_ftypes ) )
        elif topic_mask == "event":
            query = query.filter( FeedBack.ftype.IN( event_ftypes ) )

    items = query.fetch()

    feedbacks = []

    if double_range:
        for item in items:
            if item.last_access_time <= range_end:
                feedbacks.append( FeedBackInfo(item) )
    else:
        for item in items:
            feedbacks.append( FeedBackInfo(item) )

    if sorted:
        feedbacks.sort(key=lambda x: x.last_access_time, reverse=reverse_sort)

    return feedbacks

common_problem_types = [ ("discussion", "topic for discussion", 2),
                         ("request_for_stuff", "request for consumables", 5),
                         ("request_for_help", "request for help", 6),
                         ("arrange_event", "arrange an event", 7),
                         ("website_feedback", "feedback about the website", 3),
                         ("equipment_problem", "equipment problem", 4),
                         ("booking_problem", "booking problem", 9),
                         ("website_problem", "website problem", 10),
                         ("other_problem", "other problem", 8),
                         ("other", "other...", 1) ]

equipment_problem_types = [ ("consumables_error", "missing or contaminated consumables", 101),
                            ("breakage_spillage", "breakage or spillage while equipment in use", 102),
                            ("already_broken", "equipment broken or unusable before equipment in use", 103),
                            ("booking_problem_equipment", "booking problem", 104),
                            ("other_equipment", "other...", 110) ]

common_string_to_ftype = {}
common_ftype_to_string = {}
common_ftype_to_description = {}

equipment_string_to_ftype = {}
equipment_ftype_to_string = {}
equipment_ftype_to_description = {}

problem_ftypes = [4, 9, 8, 10, 101, 102, 103, 104, 110]
help_ftypes = [5, 6]
event_ftypes = [7]

for problem in equipment_problem_types:
    equipment_string_to_ftype[problem[0]] = problem[2]
    equipment_ftype_to_string[problem[2]] = problem[0]
    equipment_ftype_to_description[problem[2]] = problem[1]

for problem in common_problem_types:
    common_string_to_ftype[problem[0]] = problem[2]
    common_ftype_to_string[problem[2]] = problem[0]
    common_ftype_to_description[problem[2]] = problem[1]

class FeedBackMessage(ndb.Model):
    """Email of the user who left this message"""
    email = ndb.StringProperty(indexed=False)

    """The date and time of the message"""
    message_time = ndb.DateTimeProperty(indexed=False, auto_now_add=False, auto_now=False)

    """The actual message"""
    message = ndb.StringProperty(indexed=False)

class FeedBackMessageInfo:
    """Simple class to hold a piece of feedback message"""
    def __init__(self, message):
        self.email = unicode(message.email)
        self.message_time =  message.message_time
        self.message = unicode(message.message)

class FeedBack(ndb.Model):
    """The time when the feedback was left"""
    report_time = ndb.DateTimeProperty(indexed=True, auto_now_add=False, auto_now=False)

    """The last time that this feedback was touched"""
    last_access_time = ndb.DateTimeProperty(indexed=True, auto_now_add=False, auto_now=False)

    """The type of feedback"""
    ftype = ndb.IntegerProperty(indexed=True)

    """The ID string of any item to which this feedback is attached"""
    related_id = ndb.StringProperty(indexed=True)

    """Email of the user who reported this piece of feedback"""
    email = ndb.StringProperty(indexed=True)

    """The feedback from the user who supplied this feedback"""
    user_info = ndb.StringProperty(indexed=False)

    """Any messages that have since been added to this feedback"""
    messages = ndb.StructuredProperty(FeedBackMessage, repeated=True, indexed=False)

    """Whether or not this piece of feedback or error has been resolved"""
    is_resolved = ndb.BooleanProperty(indexed=True)

    """The email address of the person who resolved this piece of feedback"""
    resolved_email = ndb.StringProperty(indexed=False)

    """Any extra information left by the person who resolved the feedback
       (e.g. update on status etc.)"""
    resolved_info = ndb.StringProperty(indexed=False)

    """The time when the feedback was resolved"""
    resolved_time = ndb.DateTimeProperty(indexed=False, auto_now_add=False, auto_now=False)

    def setFromInfo(self, info):
        self.report_time = info.report_time
        self.last_access_time = info.last_access_time
        self.ftype = info.ftype
        self.related_id = info.related_id
        self.email = info.email
        self.user_info = info.user_info
        self.is_resolved = info.is_resolved
        self.resolved_email = info.resolved_email
        self.resolved_info = info.resolved_info
        self.resolved_time = info.resolved_time

        self.messages = []

        for message in info.messages:
            self.messages.append( FeedBackMessage(email=message.email,
                                                  message_time=message.message_time,
                                                  message=message.message) )

    @classmethod
    def stringToFType(cls, s):
        """Return the integer FType for the passed string"""
        try:
            return common_string_to_ftype[s]
        except:
            return equipment_string_to_ftype[s]

    @classmethod
    def stringToDescription(cls, s):
        """Return the human readable description of the ftype string"""
        return cls.ftypeToDescription( cls.stringToFType(s) )

    @classmethod
    def ftypeToString(cls, t):
        """Return the string representation for the passed ftype"""
        try:
            return common_ftype_to_string[t]
        except:
            return equipment_ftype_to_string[t]

    @classmethod
    def ftypeToDescription(cls, t):
        """Return the human-readable description of this ftype"""
        try:
            return common_ftype_to_description[t]
        except:
            return equipment_ftype_to_description[t]

    def feedbackID(self):
        return self.key.integer_id()

    @classmethod
    def getQuery(cls, registry=DEFAULT_FEEDBACK_REGISTRY):
        return cls.query(ancestor=feedback_key(registry))

    @classmethod
    def ancestor(cls, registry=DEFAULT_FEEDBACK_REGISTRY):
        return feedback_key(registry)

class FeedBackInfo:
    """Simple class to hold information about a piece of feedback"""
    def __init__(self, feedback=None, feedback_id=None, registry=DEFAULT_FEEDBACK_REGISTRY):
        self.report_time = None
        self.last_access_time = None
        self.ftype = None
        self.related_id = None
        self.email = None
        self.user_info = None
        self.messages = []
        self.is_resolved = False
        self.resolved_email = None
        self.resolved_info = None
        self.resolved_time = None
      
        self.feedback_id = None

        if feedback_id:
            self.feedback_id = feedback_id
            self._registry = registry
            self._CLASS = FeedBack
            feedback = self._getFromDB()

            if not feedback:
                raise DataError("There is no feedback available with feedback ID = '%s'" % feedback_id)

        if feedback:
            if feedback.report_time:
                self.report_time = feedback.report_time

            if feedback.last_access_time:
                self.last_access_time = feedback.last_access_time

            if feedback.ftype:
                self.ftype = int(feedback.ftype)

            if feedback.related_id:
                self.related_id = unicode(feedback.related_id)

            if feedback.email:
                self.email = unicode(feedback.email)

            if feedback.user_info:
                self.user_info = unicode(feedback.user_info)

            if feedback.messages:
                for message in feedback.messages:
                    self.messages.append( FeedBackMessageInfo(message) )

            if feedback.is_resolved:
                self.is_resolved = True

            if feedback.resolved_email:
                self.resolved_email = unicode(feedback.resolved_email)

            if feedback.resolved_info:
                self.resolved_info = unicode(feedback.resolved_info)

            if feedback.resolved_time:
                self.resolved_time = feedback.resolved_time

            self._CLASS = FeedBack
            self._registry = registry
            self.feedback_id = feedback.feedbackID()

    def __str__(self):
        return "FeedBackInfo( feedback_id = %s, description = %s )" % (self.feedback_id, self.description)

    def getEquipment(self):
        """Return the piece of equipment associated with this feedback. Returns "None"
           if this feedback is not about a specific piece of equipment"""
        if self.related_id:
            return bsb.equipment.get_equipment(self.related_id)
        else:
            return None

    def canBeResolvedBy(self, account):
        """Return whether or not this feedback can be resolved by the passed user"""
        if self.is_resolved:
            return False
        elif account.is_approved:
            if account.is_admin or account.email == self.email:
                return True
            else:
                item = self.getEquipment()
                if item:
                    acl = item.getACL(account)
                    if acl:
                        return acl.isAdministrator()

        return False

    def addExtraInformation(self, account, info):
        """Add extra information to this piece of feedback"""
        if not account.is_approved:
            return

        info = to_string(info)
        if not info:
            return

        now_time = bsb.get_now_time()

        item = self._getFromDB()

        message = FeedBackMessage( email=account.email, message_time=now_time, message=info )

        item.messages.append(message)
        item.last_access_time = now_time
        item.put()

        self.messages.append( FeedBackMessageInfo(message) )
        self.last_access_time = now_time

    def markAsResolved(self, account, info):
        """Mark this problem as having been resolved"""
        if self.is_resolved:
            return

        if not self.canBeResolvedBy(account):
            return

        now_time = bsb.get_now_time()
        info = to_string(info)

        item = self._getFromDB()

        message = FeedBackMessage( email=account.email, message_time=now_time, message=info )

        item.is_resolved = True
        item.last_access_time = now_time
        item.resolved_email = account.email
        item.resolved_time = now_time
        item.messages.append(message)

        item.put()

        self.is_resolved = True
        self.resolved_email = account.email
        self.resolved_time = now_time
        self.last_access_time = now_time
        self.messages.append( FeedBackMessageInfo(message) )

    def description(self):
        """Return a short description of this feedback"""
        if self.ftype:
            return "%s | %s" % (self.ftypeString(),self.user_info)
        else:
            return None

    def ftypeString(self):
        """Return the ftype descriptive string for this feedback"""
        if self.ftype:
            return FeedBack.ftypeToDescription(self.ftype)
        else:
            return None

    def severity(self):
        """Return the severity of this piece of feedback. This is a string that
           is suitable for colouring things in bootstrap, e.g. 'success', 'info', 'warning', 'danger'"""
        if self.is_resolved:
            return "success"
        elif self.ftype in help_ftypes:
            return "info"
        elif self.ftype in event_ftypes:
            return "primary"
        elif self.ftype in problem_ftypes:
            return "danger"
        else:
            return "default"

    def hasMessages(self):
        """Return whether or not this feedback has additional messages"""
        return len(self.messages) > 0

    @classmethod
    def deleteFeedBacks(cls, account, feedback_ids, registry=DEFAULT_FEEDBACK_REGISTRY):
        """Delete all of the feedback items whose IDs are in 'feedback_ids'"""

        assert_is_approved(account, "Only approved accounts can delete feedback!")
        
        keys = []

        if account.is_admin:
            for feedback_id in feedback_ids:
                try:
                    feedback_id = to_int(feedback_id)
                    if feedback_id:
                        keys.append( ndb.Key(FeedBack, feedback_id, parent=FeedBack.ancestor(registry)) )
                except:
                    pass
        else:
            for feedback_id in feedback_ids:
                try:
                    feedback_id = to_int(feedback_id)
                    key = ndb.Key(FeedBack, feedback_id, parent=FeedBack.ancestor(registry))
                    feedback = key.get()
                    if feedback:
                        if feedback.email == account.email:
                            keys.append(key)
                except:
                    pass

        if len(keys) > 0:
            ndb.delete_multi(keys)


    def deleteFeedBack(self, account):
        """Delete this piece of feedback"""
        assert_is_admin_or_user(account, self.email, 
                                "Only admin users or the feedback owner (%s) can delete this piece of feedback" % self.email)

        key = self._getKey()
            
        if key:
            key.delete()

        self.feedback_id = None
        self._CLASS = None
        self._registry = None 
        self.report_time = None
        self.last_access_time = None
        self.ftype = None
        self.related_id = None
        self.email = None
        self.user_info = None
        self.messages = []
        self.is_resolved = False
        self.feedback_id = None
        self.resolved_email = None
        self.resolved_info = None
        self.resolved_time = None

    @classmethod
    def equipmentProblemTypes(cls):
        """Return a list mapping all of the types of problem that can be reported 
           for a piece of equipment to the strings describing those types"""
        problems = []

        for problem in equipment_problem_types:
            problems.append( (problem[0], problem[1]) )

        return problems

    @classmethod
    def feedbackTypes(cls):
        """Return a list mapping all of the feedback types that can be reported 
           to the strings describing those types"""
        problems = []

        for problem in common_problem_types:
            problems.append( (problem[0], problem[1]) )

        return problems

    def _getKey(self):
        """Return the key for the datastore object that contains the data for this info"""
        if not self.feedback_id:
            return None

        return ndb.Key(self._CLASS, self.feedback_id, parent=self._CLASS.ancestor(self._registry))

    def _getFromDB(self):
        """Return the underlying datastore object that contains the data for this lab"""
        if not self.feedback_id:
            return None

        key = self._getKey()
        item = key.get()

        if not item:
            raise DataError("""There is a bug as the data for the feedback with feedback_id='%s' seems to 
                               have disappeared from the data store!""" % (self.feedback_id),
                            detail=str(self))

        return item

    def setUserInfo(self, account, user_info):
       """Allow a user to set/change the user-supplied information about this feedback"""
       assert_is_admin_or_user(account, self.email,
                               "Only admin users or the feedback owner (%s) can add extra information about this piece of feedback" % self.email)

       if self.user_info != user_info:
           item = self._getFromDB()
           if item:
               item.user_info = user_info
               now_time =bsb.get_now_time()
               item.last_access_time = now_time
               item.put()
               self.user_info = item.user_info
               self.last_access_time = now_time

    @classmethod
    def createFromEquipmentProblem(cls, account, equipment, feedback_type, message, registry=DEFAULT_FEEDBACK_REGISTRY):
        """Create a new record for a problem with a passed piece of equipment"""
        if not equipment:
            return

        ftype = FeedBack.stringToFType(feedback_type)
        title = FeedBack.ftypeToDescription(ftype)

        return cls.createFrom(account, title, "equipment_problem", 
                              related_id=equipment.idstring, message=message, registry=registry)

    @classmethod
    def createFrom(cls, account, user_info, feedback_type, related_id=None, message=None, registry=DEFAULT_FEEDBACK_REGISTRY):
        """Create a new record for the passed error"""
        if not account.is_approved:
            return

        user_info = to_string(user_info)

        if not user_info:
            raise InputError("You must supply some user information")

        ftype = FeedBack.stringToFType(feedback_type)

        now_time = bsb.get_now_time()

        feedback = FeedBack( parent=feedback_key(registry),
                             report_time=now_time,
                             last_access_time=now_time,
                             email=account.email,
                             ftype=ftype )
        
        if message:
            feedback.messages.append( FeedBackMessage(email=account.email,
                                                      message_time=now_time,
                                                      message=message) )

        if related_id:
            feedback.related_id = to_string(related_id)

        feedback.user_info = user_info

        feedback.is_resolved = False

        feedback.put()

        return FeedBackInfo(feedback)

    @classmethod
    def getUnresolvedFeedBackForEquipment(cls, item, registry=DEFAULT_FEEDBACK_REGISTRY):
        """Return all of the unresolved feedback for the passed piece of equipment"""
        if not item:
            return None

        if not item.idstring:
            return None

        items = FeedBack.getQuery(registry) \
                        .filter(FeedBack.is_resolved == False) \
                        .filter(FeedBack.related_id == item.idstring).fetch()

        if items and len(items) > 0:
            feedback = []

            for item in items:
                feedback.append( FeedBackInfo(item) )

            feedback.sort(key=lambda x: x.report_time, reverse=True)
            return feedback
        else:
            return None
