# -*- coding: utf-8 -*-

"""Module containing all classes needed to describe and manage the 
   actual equipment used by the BrisSynBio equipment scheduler"""

from google.appengine.ext import ndb
from google.appengine.api import memcache

# cgi module
import cgi

# regular expression module used to validate user account details
import re

# import the bsb module
from bsb import *

# uses the db module, which should be kept private
import bsb._db as _db

class EquipmentError(SchedulerError):
    pass

class BookingError(EquipmentError):
    pass

class PermissionError(EquipmentError):
    pass

# The default registry of equipment
DEFAULT_EQUIPMENT_REGISTRY = "bsb.equipment.equipment"

# The default registry of equipment types
DEFAULT_TYPES_REGISTRY = "bsb.equipment.equiptype"

# The default registry of labs
DEFAULT_LABS_REGISTRY = "bsb.equipment.labs"

# The default registry of equipment ACLs
DEFAULT_ACLS_REGISTRY = "bsb.equipment.equipacls"

# The default registry of bookings
DEFAULT_BOOKING_REGISTRY = "bsb.equipment.bookings"

def equipment_key(equipment_registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Constructs a Datastore key for a equipment entry.
       We use the equipment idstring as the key"""
    return ndb.Key('Equipment', equipment_registry)

def types_key(types_registry=DEFAULT_TYPES_REGISTRY):
    """Constructs a Datastore key for a equipment type entry.
       We use the equipment type idstring as the key"""
    return ndb.Key('EquipmentType', types_registry)

def labs_key(labs_registry=DEFAULT_LABS_REGISTRY):
    """Constructs a Datastore key for a lab entry.
       We use the lab idstring as the key"""
    return ndb.Key('Laboratory', labs_registry)

def acls_key(acls_registry=DEFAULT_ACLS_REGISTRY):
    """Constructs a Datastore key for an ACL entry.
       We use the equipment idstring and email as the key"""
    return ndb.Key('EquipmentACL', acls_registry)

def bookings_key(bookings_registry=DEFAULT_BOOKING_REGISTRY):
    """Constructs a Datastore key for a bookings entry for a particular piece of equipment"""
    return ndb.Key('Booking', bookings_registry)

class Booking(ndb.Model):
    """The main model for representing a booking on the system"""
    # The start time of the booking
    start_time = ndb.DateTimeProperty(indexed=True, auto_now_add=False, auto_now=False)

    # The end time of the booking
    end_time = ndb.DateTimeProperty(indexed=True, auto_now_add=False, auto_now=False)

    # The time that the booking was made
    booking_time = ndb.DateTimeProperty(indexed=False, auto_now_add=True, auto_now=False)

    # the user who made the booking
    user = ndb.StringProperty(indexed=True)

    # the project to which this booking is assigned
    project = ndb.StringProperty(indexed=True)

    # the google calendar ID for this booking
    gcal_id = ndb.StringProperty(indexed=False)

    # the status of the booking
    status = ndb.IntegerProperty(indexed=True)

    # extra information about the booking (e.g. temperatures etc.)
    information = ndb.JsonProperty(indexed=False)

    # the requirements needed to be supplied by the user
    requirements = ndb.IntegerProperty(indexed=False)

    def setFromInfo(self, info):
        self.start_time = info.start_time
        self.end_time = info.end_time
        self.user = info.email
        self.project = info.project
        self.booking_time = info.booking_time
        self.status = info.status
        self.information = info.information
        self.requirements = info.requirements

    def setInformation(self, key, value):
        """Set the piece of information with key 'key' to value 'value'"""
        if not self.information:
            self.information = {}

        self.information[key] = value

    def getInformation(self, key):
        """Return the value of the piece of information with key 'key', or
           None if no such information exists"""
        try:
            return self.information[key]
        except:
            return None               

    def equipment(self):
        return self.key.parent().string_id()

    def email(self):
        return self.user

    def bookingID(self):
        return self.key.integer_id()

    @classmethod
    def getQuery(cls, registry=DEFAULT_BOOKING_REGISTRY):
        return cls.query(ancestor=bookings_key(registry))

    @classmethod
    def getEquipmentQuery(cls, equipment_idstring, registry=DEFAULT_BOOKING_REGISTRY):
        return cls.query(ancestor=ndb.Key(Equipment,equipment_idstring,parent=bookings_key(registry)))

    @classmethod
    def ancestor(cls, registry=DEFAULT_BOOKING_REGISTRY):
        return bookings_key(registry)

    @classmethod
    def ancestorForEquipment(cls, equipment_idstring, registry=DEFAULT_BOOKING_REGISTRY):
        return ndb.Key(Equipment,equipment_idstring,parent=bookings_key(registry))

    @classmethod
    def reserved(cls):
        return 1

    @classmethod
    def cancelled(cls):
        return 0

    @classmethod
    def confirmed(cls):
        return 2

    @classmethod
    def pendingAuthorisation(cls):
        return 3

    @classmethod
    def deniedAuthorisation(cls):
        return 4

booking_types = [ ("booked by the minute", "minute"),
                  ("booked by the hour", "hour"),
                  ("booked for a morning or an afternoon", "half-day"),
                  ("booked by the day", "day"),
                  ("booked by the week", "week") ]

class BookingConstraint(ndb.Model):
    """The constraints that apply when making a booking, e.g. not weekends, no overnight etc."""

    # An information string showed to the user to provide
    # a human-readable description of the booking constraints
    booking_info = ndb.StringProperty(indexed=False)

    # the start of the allowed booking range, if a range applies
    allowed_range_start = ndb.TimeProperty(indexed=False)

    # the end of the allowed booking range, if a range applies
    allowed_range_end = ndb.TimeProperty(indexed=False)

    # the minimum length of a booking, in minutes
    min_booking_time = ndb.IntegerProperty(indexed=False)

    # the maximum length of a booking, in minutes
    max_booking_time = ndb.IntegerProperty(indexed=False)

    # the list of days on which bookings are allowed (true or false, Mon-Sun is index 0-6)
    allowed_days = ndb.BooleanProperty(indexed=False, repeated=True)

    # the units of time for this booking, e.g. 5 minutes, hours, days, weeks
    booking_unit = ndb.IntegerProperty(indexed=False)

    @classmethod
    def bookableUnitTypes(cls):
        return booking_types

    @classmethod
    def bookableUnitTypeByIndex(cls, i):
        return booking_types[i]

    @classmethod
    def bookableUnitTypeByName(cls, name):
        for typ in booking_types:
            if typ[1] == name:
                return typ

        return None

    @classmethod
    def bookableUnitIDFromName(cls, name):
        for i in range(0,len(booking_types)):
            if booking_types[i][1] == name:
                return i

        return 0

    @classmethod
    def createFrom(cls, con):
        if not con:
            return None

        b = BookingConstraint()
        b.booking_unit = 0

        if con.booking_info:
            b.booking_info = con.booking_info

        if con.booking_unit:
            b.booking_unit = con.booking_unit

        if con.has_range:
            b.allowed_range_start = con.allowed_range_start
            b.allowed_range_end = con.allowed_range_end

        if con.min_booking_time:
            b.min_booking_time = con.min_booking_time

        if con.max_booking_time:
            b.max_booking_time = con.max_booking_time

        b.allowed_days = []

        for day in con.allowed_days:
            b.allowed_days.append(day)
        
        return b

class BookingConstraintInfo:
    def __init__(self, con=None):
        self.booking_info = None
        self.allowed_range_start = None
        self.allowed_range_end = None
        self.has_range = False
        self.min_booking_time = None
        self.max_booking_time = None
        self.booking_unit = 0
        self.allowed_days = [True, True, True, True, True, True, True]

        if con:
            if con.booking_info:
                self.booking_info = con.booking_info

            if con.allowed_range_start:
                self.allowed_range_start = con.allowed_range_start
                self.allowed_range_end = con.allowed_range_end
                self.has_range = True

            if con.booking_unit:
                self.booking_unit = con.booking_unit
                self.booking_unit_string = BookingConstraint.bookableUnitTypeByIndex(con.booking_unit)[0]
            else:
                self.booking_unit = 0
                self.booking_unit_string = BookingConstraint.bookableUnitTypeByIndex(0)[0]

            if con.min_booking_time:
                self.min_booking_time = con.min_booking_time

            if con.max_booking_time:
                self.max_booking_time = con.max_booking_time

            if con.allowed_days:
                self.allowed_days = []
                for day in con.allowed_days:
                    self.allowed_days.append(day)

    def _availableDaysString(self):
        """Return a human-readable string of the days on which booking is allowed"""
        
        # check for all days
        is_working_week = True
        is_full_week = True

        for i in range(0,7):
            if not self.allowed_days[i]:
                is_full_week = False
                if i < 5:
                    is_working_week = False
                    break

        if is_full_week:
            return "any day"
        elif is_working_week:
            return "Monday-Friday"
        else:
            days = []
            if self.allowed_days[0]:
                days.append( "Monday" )
            if self.allowed_days[1]:
                days.append( "Tuesday" )
            if self.allowed_days[2]:
                days.append( "Wednesday" )
            if self.allowed_days[3]:
                days.append( "Thursday" )
            if self.allowed_days[4]:
                days.append( "Friday" )
            if self.allowed_days[5]:
                days.append( "Saturday" )
            if self.allowed_days[6]:
                days.append( "Sunday" )

            return ", ".join(days)

    def calendarType(self):
        """Return the appropriate calendar type for these constraints"""
        unit = booking_types[self.booking_unit][1]

        if unit in ("day", "week"):
            return "month"
        else:
            return "week"        

    def bookByDate(self):
        """Return whether or not booking is only by date (day and week bookings)"""
        unit = booking_types[self.booking_unit][1]
        return unit in ("day","week")        

    def daysOfWeekDisabled(self, is_start=False, is_end=False):
        """Return an array of the days of the week that are disabled, in a format that can
           be understood by the date picker"""

        unit = booking_types[self.booking_unit][1]

        if unit == "week":
            if is_start:
                return "[0,2,3,4,5,6]"
            elif is_end:
                return "[0,1,2,3,4,6]"

        output = []

        for i in range(0,6):
            if not self.allowed_days[i]:
                output.append( str(i+1) )

        if not self.allowed_days[6]:
            output.append( str(0) )

        if len(output) > 0:
            return "[%s]" % ",".join(output)
        else:
            return None

    def constraintsString(self):
        """Return a human-readable string detailing the constraints that apply to any booking"""
        output = []

        unit = booking_types[self.booking_unit]

        output.append( "This equipment is available to be %s." % unit[0] ) 

        if unit[1] == "half-day":
            output.append("Half-day bookings allow access between either 9am-1pm, or 2pm-6pm.")

        elif unit[1] == "day":
            output.append("Day bookings allow access between 9am-6pm.")

        elif unit[1] == "week":
            output.append("Week bookings allow access between Monday-Friday, 9am-6pm.")

        if self.has_range and unit[1] in ("minute", "hour"):
            output.append( "Bookings allow access between %s-%s." % \
                              (self.allowed_range_start.strftime("%I:%M%p"),
                               self.allowed_range_end.strftime("%I:%M%p")) )

        output.append( "Bookings can be made on %s." % self._availableDaysString() )
       
        if self.min_booking_time:
            output.append( "The minimum amount of time you can book is %s." % mins_to_string(self.min_booking_time) )
        if self.max_booking_time:
            output.append( "The maximum amount of time you can book is %s." % mins_to_string(self.max_booking_time) )

        return "\n".join(output)

    def validate(self, start_time, end_time):
        """Validate that the passed start_time and end_time are valid, and also 
           sanitise them so that they match up with the booking unit"""

        # first, ensure that the booking is being made on an allowed day
        if not self.allowed_days[start_time.isoweekday()-1]:
            raise BookingError( "You cannot start your booking on a %s. Allowable days are %s." % \
                                 (start_time.strftime("%A"), self._availableDaysString()),
                                 detail=start_time )

        if not self.allowed_days[end_time.isoweekday()-1]:
            raise BookingError( "You cannot end your booking on a %s. Allowable days are %s." % \
                                 (end_time.strftime("%A"), self._availableDaysString()),
                                 detail=end_time )

        # next, fix the start and end times to be of the right type for the 
        # booking unit
        unit = booking_types[self.booking_unit][1]

        if unit != "minute":
            # times can only start and stop on the hour
            start_time = start_time.replace( minute=0 )
            end_time = end_time.replace( minute=0 )

        if unit == "half-day":
            # the two slots are 9am-1pm and 2pm-6pm
            morning_start = to_utc( start_time.replace( hour=9, tzinfo=GMT_TZ() ) )
            morning_end = to_utc( start_time.replace( hour=13, tzinfo=GMT_TZ() ) )
            
            if start_time >= morning_start and start_time < morning_end:
                start_time = morning_start
            else:
                afternoon_start = to_utc( start_time.replace( hour=14, tzinfo=GMT_TZ() ) )
                afternoon_end = to_utc( start_time.replace( hour=18, tzinfo=GMT_TZ() ) )

                if start_time >= afternoon_start and start_time < afternoon_end:
                    start_time = afternoon_start
                elif start_time < morning_start:
                    raise BookingError( "Cannot book a half-day start time that is before 9am",
                                        detail=(start_time, morning_start, morning_end) )
                elif start_time >= afternoon_end:
                    raise BookingError( "Cannot book a half-day start time that is after 6pm",
                                        detail=(start_time, afternoon_start, afternoon_end) )
                else:
                    raise BookingError( "Cannot book a half-day start time that is during the lunch break (1pm-2pm)",
                                        detail=(start_time, morning_end, afternoon_start) )

            morning_start = to_utc( end_time.replace( hour=9, tzinfo=GMT_TZ() ) )
            morning_end = to_utc( end_time.replace( hour=13, tzinfo=GMT_TZ() ) )

            if end_time > morning_start and end_time <= morning_end:
                end_time = morning_end
            else:
                afternoon_start = to_utc( end_time.replace( hour=14, tzinfo=GMT_TZ() ) )
                afternoon_end = to_utc( end_time.replace( hour=18, tzinfo=GMT_TZ() ) )

                if end_time > afternoon_start and end_time <= afternoon_end:
                    end_time = afternoon_end
                elif end_time <= morning_start:
                    raise BookingError( "Cannot book a half-day end time that is before 9am",
                                        detail=(end_time, morning_start, morning_end) )
                elif end_time > afternoon_end:
                    raise BookingError( "Cannot book a half-day end time that is after 6pm",
                                        detail=(end_time, afternoon_start, afternoon_end) )
                else:
                    raise BookingError( "Cannot book a half-day end time that is during the lunch break (1pm-2pm)",
                                        detail=(end_time, morning_end, afternoon_end) )

        elif unit == "day":
            start_time = to_utc( start_time.replace( hour=9, tzinfo=GMT_TZ() ) )
            end_time = to_utc( end_time.replace( hour=18, tzinfo=GMT_TZ() ) )

        elif unit == "week":
            start_time = to_utc( start_time.replace( hour=9, tzinfo=GMT_TZ() ) )
            end_time = to_utc( end_time.replace( hour=18, tzinfo=GMT_TZ() ) )

            # now ensure that start_time is a Monday and end_time is a Friday
            if start_time.isoweekday() != 1:
                # go back to the last Monday
                start_time = start_time - datetime.timedelta( days = (start_time.isoweekday() - 1) )

            if end_time.isoweekday() < 5:
                # go forward to Friday
                end_time = end_time + datetime.timedelta( days = (5 - end_time.isoweekday()) )
            elif end_time.isoweekday() > 5:
                # go forward to next Friday
                end_time = end_time + datetime.timedelta( days = (12 - end_time.isoweekday()) )

        if self.has_range and unit in ("minute", "hour"):
            # validate that the start_time and end_time are within the required range. We don't
            # do this for non-time slots (e.g. half-day, day and week)
            day_start = to_utc( start_time.replace(hour=self.allowed_range_start.hour, 
                                                   minute=self.allowed_range_start.minute,
                                                   tzinfo=GMT_TZ() ) )
            day_end = to_utc( start_time.replace(hour=self.allowed_range_end.hour, 
                                                 minute=self.allowed_range_end.minute,
                                                 tzinfo=GMT_TZ() ) )

            if start_time < day_start:
                raise BookingError( "You cannot arrange a booking that starts before %s." \
                                      % self.allowed_range_start.strftime("%I:%M%p"),
                                    detail=(start_time, day_start, self.allowed_range_start) )

            elif start_time >= day_end:
                raise BookingError( "You cannot arrange a booking that starts after %s." \
                                      % self.allowed_range_end.strftime("%I:%M%p"),
                                    detail=(start_time, day_end, self.allowed_range_end) )

            day_start = to_utc( end_time.replace(hour=self.allowed_range_start.hour, 
                                                 minute=self.allowed_range_start.minute,
                                                 tzinfo=GMT_TZ() ) )
            day_end = to_utc( end_time.replace(hour=self.allowed_range_end.hour, 
                                               minute=self.allowed_range_end.minute,
                                               tzinfo=GMT_TZ() ) )

            if end_time <= day_start:
                raise BookingError( "You cannot arrange a booking that ends before %s." \
                                      % self.allowed_range_start.strftime("%I:%M%p"),
                                    detail=(end_time, day_start, self.allowed_range_start) )

            elif end_time > day_end:
                raise BookingError( "You cannot arrange a booking that ends after %s." \
                                      % self.allowed_range_end.strftime("%I:%M%p"),
                                    detail=(end_time, day_end, self.allowed_range_end) )

        if start_time > end_time:
            tmp = start_time
            start_time = end_time
            end_time = tmp

        if self.min_booking_time or self.max_booking_time:
            # ensure that the amount of time booked (in minutes) is above the minimum required
            delta_mins = (end_time - start_time).total_seconds() / 60

            if self.min_booking_time and (delta_mins < self.min_booking_time):
                raise BookingError( "Your booking is too short (%s). It needs to be at least %s." \
                                    % (mins_to_string(delta_mins), mins_to_string(self.min_booking_time)),
                                    detail=(start_time,end_time) )

            elif self.max_booking_time and (delta_mins > self.max_booking_time):
                raise BookingError( "Your booking is too long (%s). It needs to be less than %s." \
                                    % (mins_to_string(delta_mins), mins_to_string(self.max_booking_time)),
                                    detail=(start_time,end_time) )

        return (start_time, end_time)


    def setBookableUnit(self, account, acl, equipment, unit):
        """Set the bookable time unit for this piece of equipment"""
        acl.assertIsAdministrator(account)

        unit = BookingConstraint.bookableUnitIDFromName(to_string(unit))

        if unit != self.booking_unit:
            item = equipment._getFromDB()
            item.constraints.booking_unit = unit
            item.put()

            self.booking_unit = unit
            self.booking_unit_string = BookingConstraint.bookableUnitTypeByIndex(unit)[0]         

    def setInformation(self, account, acl, equipment, info):
        """Set the user-facing information describing these booking constraints"""
        info = to_string(info)

        if not info:
            return

        acl.assertIsAdministrator(account)

        item = equipment._getFromDB()
        item.constraints.booking_info = info
        item.put()

        self.booking_info = info

    def setBookableDays(self, account, acl, equipment, days):
        """Set the days that can be booked. This should be a list of seven True/False values
           (Monday-Sunday)"""

        acl.assertIsAdministrator(account)

        if not len(days) == 7:
            raise ProgramBug( "You need to supply a list of seven True/False values", detail=days )

        item = equipment._getFromDB()
        item.constraints.allowed_days = []
        self.allowed_days = []

        for day in days:
            item.constraints.allowed_days.append( day is True )
            self.allowed_days.append( day is True )

        item.put()

    def setMinimumTime(self, account, acl, equipment, mintime):
        """Set the minimum amount of time that can be booked - the amount of time in minutes should be passed"""

        acl.assertIsAdministrator(account)

        mintime = to_int(mintime)

        if not mintime:
            mintime = None

        if mintime != self.min_booking_time:
            item = equipment._getFromDB()
            item.constraints.min_booking_time = mintime
            self.min_booking_time = mintime
            item.put()

    def setMaximumTime(self, account, acl, equipment, maxtime):
        """Set the maximum amount of time that can be booked - the amount of time in minutes should be passed"""

        acl.assertIsAdministrator(account)

        maxtime = to_int(maxtime)

        if not maxtime:
            maxtime = None

        if maxtime != self.max_booking_time:
            item = equipment._getFromDB()
            item.constraints.max_booking_time = maxtime
            self.max_booking_time = maxtime
            item.put()

    def removeBookingRange(self, account, acl, equipment):
        """Switch off the use of a booking range for this piece of equipment"""
        acl.assertIsAdministrator(account)

        if self.has_range:
            item = equipment._getFromDB()
            item.constraints.allowed_range_start = None
            item.constraints.allower_range_end = None
            item.put()
            self.allowed_range_start = None
            self.allowed_range_end = None
            self.has_range = False

    def setBookingRange(self, account, acl, equipment, range_start, range_end):
        """Set the booking range of this equipment to 'range_start' -> 'range_end'"""
        acl.assertIsAdministrator(account)

        range_start = to_time(range_start)
        range_end = to_time(range_end)

        if not (range_start and range_end):
            return

        if range_start > range_end:
            tmp = range_start
            range_start = range_end
            range_end = tmp

        if range_start != self.allowed_range_start or range_end != self.allowed_range_end:
            item = equipment._getFromDB()
            item.constraints.allowed_range_start = range_start
            item.constraints.allowed_range_end = range_end
            item.put()
            self.allowed_range_start = range_start
            self.allowed_range_end = range_end
            self.has_range = True


class EquipmentReq(ndb.Model):
    """An individual equipment booking requirement"""
    # The type of requirement - temperature, speed, number, string etc.
    reqtype = ndb.StringProperty(indexed=False)

    # The name of the requirement (what is presented to the user)
    reqname = ndb.StringProperty(indexed=False)

    # The range of allowed values for this requirement. If this 
    # is not specified, then any value is valid
    allowed_values = ndb.StringProperty(indexed=False)

    # Any help attached to this requirement (e.g. to provide a long
    # description of what this is
    reqhelp = ndb.StringProperty(indexed=False)

class EquipmentReqInfo:
    def __init__(self, req):
        self.reqtype = None
        self.reqname = None
        self.reqid = None
        self.allowed_values = None
        self.reqhelp = None

        if req:
            if req.reqtype:
                self.reqtype = unicode(req.reqtype)

            if req.reqname:
                self.reqname = unicode(req.reqname)
                self.reqid = name_to_idstring(self.reqname)

            if req.allowed_values:
                self.allowed_values = unicode(req.allowed_values)
                self.allowed_values = re.sub(r"\.0"," ",re.sub(r"\.0,",",",re.sub(r"\.0$","",self.allowed_values)))

            if req.reqhelp:
                self.reqhelp = unicode(req.reqhelp)

        self.validator = None

    def __str__(self):
        return "EquipmentReqInfo(reqtype='%s', reqname='%s')" % (self.reqtype, self.reqname)

    def getValidator(self):
        """Return the validator for this requirement"""
        if self.validator:
            return self.validator

        if self.allowed_values:
            self.validator = AllowedValues(self.allowed_values,self.reqtype)
            return self.validator

        return AllowedValues()

    def isText(self):
        """Return whether or not this value is a piece of text"""
        return RequirementTypes().isText(self.reqtype)

    def isInteger(self):
        """Return whether or not this value is an integer"""
        return RequirementTypes().isInteger(self.reqtype)

    def getUnitString(self):
        """Return the human readable string for the units of this type"""
        return RequirementTypes().getUnits(self.reqtype)

    def getValueHelpString(self):
        """Return a help string for helping suggest the desirable values"""
        v = self.getValidator()

        if v:
            return v.getHelpString()
 
        elif self.isText():
            return "type here..."

        elif self.isInteger():
            return "type any whole number (integer) here..."

        else:
            unit_string = self.getUnitString()

            if unit_string:
                return "type any value in units of %s here..." % unit_string
            else:
                return "type any number here..."

    def hasDiscreteValues(self):
        """Return whether or not this requirement specifies discrete values"""
        return self.getValidator().hasDiscreteValues()

    def discreteValues(self):
        """Return the set of discrete values for this requirement"""
        return self.getValidator().discreteValues()

    def validate(self, value):
        """Validate that the passed value is acceptable for this requirement"""
        if not self.getValidator().isValid(value):
            raise InputError("The passed value '%s' does not fit into the valid range of values %s" \
                             % (value, self.validator.toString()))

    def processResponse(self, value):
        """Process and validate the passed value and return it"""
        self.validate(value)

        unit_string = self.getUnitString()

        if unit_string and value.find(unit_string) == -1:
            return "%s %s" % (value,unit_string)
        else:
            return value

class EquipmentReqs(ndb.Model):
    """The requirements that must be provided by the user when making a booking"""
    # A help or description paragraph that is printed with the requirements
    intro = ndb.StringProperty(indexed=False)

    # The list of requirements for this booking
    requirements = ndb.StructuredProperty(EquipmentReq, repeated=True, indexed=False)

    # Whether or not this booking has to be authorised
    needs_authorisation = ndb.BooleanProperty(indexed=False)

    def setFromInfo(self, info):
        self.intro = info.intro
        self.needs_authorisation = info.needs_authorisation

        self.requirements = []

        for requirement in info.requirements:
            self.requirements.append( EquipmentReq(reqtype=requirement.reqtype,
                                                   reqname=requirement.reqname,
                                                   allowed_values=requirement.allowed_values,
                                                   reqhelp=requirement.reqhelp) )

    def requirementsID(self):
        return self.key.integer_id()

    @classmethod
    def getQuery(cls, registry=DEFAULT_EQUIPMENT_REGISTRY):
        return cls.query(ancestor=equipment_key(registry))

    @classmethod
    def ancestor(cls, registry=DEFAULT_EQUIPMENT_REGISTRY):
        return equipment_key(registry)

# List of all types of requirement. ID string, User string, units, whether_or_not_is_number
requirement_types = [ ("temperature", "temperature", "celsius", True),
                      ("spin_speed", "spin speed", "rpm", True),
                      ("string", "text", None, False),
                      ("number", "number", None, True),
                      ("integer", "whole number", None, True) ]

class RequirementTypes:
    def __init__(self):
        self.types = []
        for typ in requirement_types:
            self.types.append( typ[0] )

    def isInteger(self, typ):
        """Return whether or not the passed type is an integer"""
        return typ == "integer"

    def isText(self, typ):
        """Return whether or not the passed type is text"""
        return typ is None or typ == "string"

    def isNumber(self, typ):
        """Return whether or not the passed type is a number"""
        for t in requirement_types:
            if t[0] == typ:
                return t[3]

        return False

    def getUnits(self, typ):
        """Return the units for the passed type"""
        for t in requirement_types:
            if t[0] == typ:
                return t[2]

        return None

    def typeToString(self, typ, include_units=True):
        """Return the string representing the requirement type 'typ'. Include
           the units in the string if 'include_units' is True"""
        typ = to_string(typ)
        if not typ:
            return None

        for t in requirement_types:
            if t[0] == typ:
                if t[2] and include_units:
                    return "%s in %s" % (t[1],t[2])
                else:
                    return t[1]

        raise ProgramBug("There is no requirement with key '%s'" % typ)

class AllowedValues:
    def __init__(self, vals=None, units=None):
        """Process the passed string and turn it into a list of allowed values"""
        
        self.units = units

        vals = to_string(vals)

        if vals:
            vals = vals.lower()

        if vals == "all" or not vals:
            # match everything
            self.allowed_values = None
            self.has_range = True
            self.is_unbounded = True
            return

        values = []

        is_error = False
        has_range = False
        is_unbounded = False

        for value in vals.split(","):
            value = value.replace(" ","").lstrip().rstrip()

            m = re.search("(-?\d+\.?\d*)-(-?\d+\.?\d*)", value)

            if m:
                # we have a range of values
                start = float(m.groups()[0])
                end = float(m.groups()[1])

                if start == end:
                    values.append( start )
                elif start < end:
                    values.append( (start,end) )
                    has_range = True
                else:
                    values.append( (end,start) )
                    has_range = True
            else:
                m = re.search("(-?\d+\.?\d*)\+", value)

                if m:
                    # we have found a X+ value
                    start = float(m.groups()[0])
                    values.append( (start, '+') )
                    has_range = True
                    is_unbounded = True
                else:
                    try:
                        values.append( float(value.lstrip().rstrip()) )
                    except:
                        is_error = True
                        break

        if is_error:
            raise InputError( """Cannot understand the range of values in '%s'. You should either
                provide a comma-separated list of numbers (e.g. '10, 20, 30, 40'), or ranges of 
                numbers (e.g. '10-40') or use '+' to indicate all numbers greater than a value
                (e.g. '30+'), or use 'all' to indicate matching all values.""" % vals )

        self.allowed_values = values
        self.has_range = has_range
        self.is_unbounded = is_unbounded

    def getUnitsString(self):
        """Return the human-readable string for these units"""
        return RequirementTypes().getUnits(self.units)

    def toString(self, include_units=False):
        """Return a string representation of the allowed values. Returns 'None' if
           all values are allowable"""
        if self.allowed_values:

            unit_string = self.getUnitsString()

            s = []

            if unit_string:
                for value in self.allowed_values:
                    if not isinstance(value,tuple):
                        s.append( "%s %s" % (re.sub(r"\.0$","",str(value)),unit_string) )
                    elif value[1] == '+':
                        s.append( "%s+ %s" % (re.sub(r"\.0$","",str(value[0])),unit_string))
                    else:
                        s.append( "%s %s - %s %s" % (re.sub(r"\.0$","",str(value[0])), unit_string, \
                                                     re.sub(r"\.0$","",str(value[1])), unit_string))
            else:
                for value in self.allowed_values:
                    if not isinstance(value,tuple):
                        s.append( str(value) )
                    elif value[1] == '+':
                        s.append( "%s+" % value[0])
                    else:
                        s.append( "%s - %s" % (value[0],value[1]))

            return ", ".join(s)

        else:
            return None 

    def isInteger(self):
        return self.units == "integer"

    def hasRange(self):
        """Return whether or not this accepts a range of values"""
        return not self.hasDiscreteValues()

    def hasDiscreteValues(self):
        """Return whether or not this accepts only one of a set of discrete values"""
        if (not self.is_unbounded) and (self.units == "integer"):
            return True
        else:
            return not self.has_range

    def getHelpString(self):
        """Return a string providing help about this range"""
        if self.allowed_values:
            unit_string = self.getUnitsString()
            if unit_string:
                return "value in units of %s, allowed values are [ %s ]" % (unit_string, self.toString(False))
            else:
                return "allowed values are [ %s ]" % self.toString(False)
        else:
            return "type here..."

    def discreteValues(self):
        """Return the discrete values accepted by this range. Note that hasDiscreteValues
           must be true"""
        if not self.hasDiscreteValues():
            raise ProgramBug( """You cannot get discrete values from a set of allowed values that has a range!""" )

        vals = []

        unit_string = self.getUnitsString()

        if unit_string:
            for value in self.allowed_values:
                v = "%s %s" % (re.sub(r"\.0$","",str(value)),unit_string)
                vals.append( (v,v) )

        elif self.units == "integer":
            for value in self.allowed_values:
                if isinstance(value,tuple):
                    for i in range(int(value[0]),int(value[1])+1):
                        vals.append( (i,i) )
                else:
                    vals.append(int(value))
        else:
            for value in self.allowed_values:
                v = re.sub(r"\.0$","",str(value))
                vals.append( (v,v) )

        return vals

    def isValid(self, value):
        """Validate that the passed value is valid"""
        if not self.allowed_values:
            return True

        try:
            unit_string = self.getUnitsString()

            if unit_string:
                value = value.replace(unit_string, "")

            value = float(value.lstrip().rstrip())

            for val in self.allowed_values:
                if isinstance(val, tuple):
                    if val[1] == '+':
                        if value >= val[0]:
                            return True
                    else:
                        if value >= val[0] and value <= val[1]:
                            return True
                else:
                    if val == value:
                        return True

            return False

        except:
            return False

class EquipmentReqsInfo:
    def __init__(self, reqs=None, reqs_id=None, registry=DEFAULT_EQUIPMENT_REGISTRY):
        self.intro = None
        self.requirements = []
        self.needs_authorisation = False

        self.reqs_id = None

        if reqs_id:
            self.reqs_id = reqs_id
            self._registry = registry
            self._CLASS = EquipmentReqs
            reqs = self._getFromDB()

            if not reqs:
                raise DataError("There are no requirements available with ID = '%s'" % reqs_id)

        if reqs:
            if reqs.intro:
                self.intro = unicode(reqs.intro)

            if reqs.needs_authorisation:
                self.needs_authorisation = True

            if reqs.requirements:
                for requirement in reqs.requirements:
                    self.requirements.append( EquipmentReqInfo(requirement) )

            self._CLASS = EquipmentReqs
            self._registry = registry
            self.reqs_id = reqs.requirementsID()

    def setNeedsAuthorisation(self, account, acl, needs_authorisation):
        """Set whether or not bookings using this piece of equipment need to be authorised
           by an equipment owner before becoming valid"""
        acl.assertIsAdministrator(account)

        if needs_authorisation != self.needs_authorisation:
            reqs = self._getFromDB()
            reqs.needs_authorisation = needs_authorisation
            reqs.put()
            self.needs_authorisation = needs_authorisation

    def setIntroduction(self, account, acl, introduction):
        """Set the introduction text for booking this piece of equipment"""
        acl.assertIsAdministrator(account)

        introduction = to_string(introduction)

        if introduction != self.intro:
            reqs = self._getFromDB()
            reqs.intro = introduction
            reqs.put()
            self.intro = introduction

    def moveDown(self, account, acl, req_name):
        """Move the named requirement up the list of requirements"""
        acl.assertIsAdministrator(account)

        req_name = to_string(req_name)

        if not req_name or len(self.requirements) < 2:
            return

        index = -1

        for i in range(0, len(self.requirements)):
            if self.requirements[i].reqname == req_name:
                index = i

        if index == len(self.requirements)-1:
            return

        item = self._getFromDB()

        r = item.requirements.pop(index)
        item.requirements.insert(index+1, r)
        item.put()

        r = self.requirements.pop(index)
        self.requirements.insert(index+1, r)

    def moveUp(self, account, acl, req_name):
        """Move the named requirement up the list of requirements"""
        acl.assertIsAdministrator(account)

        req_name = to_string(req_name)

        if not req_name or len(self.requirements) < 2:
            return

        index = -1

        for i in range(0, len(self.requirements)):
            if self.requirements[i].reqname == req_name:
                index = i

        if index < 1:
            return

        item = self._getFromDB()

        r = item.requirements.pop(index)
        item.requirements.insert(index-1, r)
        item.put()

        r = self.requirements.pop(index)
        self.requirements.insert(index-1, r)

    def deleteRequirement(self, account, acl, req_name):
        """Delete the requirement called 'req_name'"""
        acl.assertIsAdministrator(account)

        req_name = to_string(req_name)

        if not req_name:
            return

        index = -1

        for i in range(0, len(self.requirements)):
            if self.requirements[i].reqname == req_name:
                index = i
                break

        if index != -1:
            item = self._getFromDB()
            item.requirements.pop(index)
            item.put()

            self.requirements.pop(index)

    def setRequirement(self, account, acl, req_name, req_type, allowed_values=None, req_help=None):
        """Set (or add) the passed requirement"""
        acl.assertIsAdministrator(account)

        req_name = to_string(req_name) 
        req_type = to_string(req_type)
        allowed_values = AllowedValues(allowed_values).toString()
        req_help = to_string(req_help)

        if not (req_name and req_type):
            return

        index = -1

        for i in range(0, len(self.requirements)):
            if self.requirements[i].reqname == req_name:
                if req_type == self.requirements[i].reqtype and req_help == self.requirements[i].reqhelp and \
                   allowed_values == self.requirements[i].allowed_values:
                    # nothing to do
                    return

                index = i
                break

        item = self._getFromDB()

        if index == -1:
            item.requirements.append( EquipmentReq( reqname=req_name,
                                                    reqtype=req_type,
                                                    allowed_values=allowed_values,
                                                    reqhelp=req_help ) )
            index = len(item.requirements) - 1
        else:
            item.requirements[index].reqname = req_name
            item.requirements[index].reqtype = req_type
            item.requirements[index].allowed_values = allowed_values
            item.requirements[index].reqhelp = req_help

        item.put()

        self.requirements.append( EquipmentReqInfo(item.requirements[index]) )                

    def duplicateAndStore(self, registry=None):
        """Duplicate these requirements and store them into a new EquipmentReqs object"""
        if self.reqs_id:
            dup = EquipmentReqs( parent=equipment_key(registry),
                                 intro=self.intro,
                                 needs_authorisation=self.needs_authorisation )

            for requirement in self.requirements:
                dup.requirements.append( EquipmentReq(reqtype=requirement.reqtype,
                                                      reqname=requirement.reqname,
                                                      reqhelp=requirement.reqhelp) )

            dup.put()
            return EquipmentReqsInfo(dup)

    def processResponse(self, response, is_demo=False, registry=DEFAULT_BOOKING_REGISTRY):
        """Process the response from the user so that the requirements can be created"""
        if not is_demo:
            user_reqs = BookingReqs(parent=BookingReqs.ancestor(registry),
                                    reqid=self.reqs_id,
                                    is_authorised=(not self.needs_authorisation))
        else:
            user_reqs = BookingReqsInfo()
            user_reqs.reqid = self.reqs_id
            is_authorised=(not self.needs_authorisation)

        if len(self.requirements) > 0:
            user_reqs.requirements = []

            errors = []

            for requirement in self.requirements:
                try:
                    value = to_string(response.get(requirement.reqid,None))

                    if not value:
                        raise InputError("You must supply a value for '%s'" % requirement.reqname)

                    value = requirement.processResponse(value)
                    user_reqs.requirements.append( BookingReq(reqname=requirement.reqname,
                                                              reqvalue=value) )
                except Exception as e:
                    errors.append(e)

            if len(errors) > 0:
                raise InputError("There were problems processing the user input", detail=errors)

        if not is_demo:
            user_reqs.put()
            return BookingReqsInfo(reqs_id=user_reqs.requirementsID(), registry=registry)
        else:
            return user_reqs

    @classmethod
    def createFrom(cls, reqs, registry=DEFAULT_BOOKING_REGISTRY):
        """Create this object from the passed requirements"""
        if reqs:
            booking = BookingReqs(parent=BookingReqs.ancestor(registry),
                                  is_authorised=(not reqs.needs_authorisation))

            if reqs.requirements:
                booking.requirements = []

                for requirement in reqs.requirements:
                    booking.append( BookingReq(reqname=requirement.reqname,
                                               reqvalue=None) )

            booking.put()
            return BookingReqsInfo(booking,registry)
        else:
            return None

    def _getKey(self):
        """Return the key for the datastore object that contains the data for this info"""
        if not self.reqs_id:
            return None

        return ndb.Key(self._CLASS, int(self.reqs_id), parent=self._CLASS.ancestor(self._registry))

    def _getFromDB(self):
        """Return the underlying datastore object that contains the data for this lab"""
        if not self.reqs_id:
            return None

        key = self._getKey()
        item = key.get()

        if not item:
            raise DataError("""There is a bug as the data for the Equipment requirements object with ID='%s' seems to 
                               have disappeared from the data store!""" % (self.reqs_id),
                            detail=str(self))

        return item

class BookingReq(ndb.Model):
    """An individual requirement and value for the booking"""
    # name of the requirement as specified with the equipment
    reqname = ndb.StringProperty(indexed=False)

    # the value of the requirement, as provided by the user
    reqvalue = ndb.StringProperty(indexed=False)

class BookingReqInfo:
    def __init__(self, req):
        self.reqname = None
        self.reqvalue = None

        if req:
            if req.reqname:
                self.reqname = unicode(req.reqname)

            if req.reqvalue:
                self.reqvalue = unicode(req.reqvalue)

class BookingReqs(ndb.Model):
    """The requirements provided by the user when they made a booking"""
    # the ID of the EquipmentReqs to which this is attached
    reqid = ndb.IntegerProperty(indexed=False)

    # all of the requirements and values
    requirements = ndb.StructuredProperty(BookingReq, repeated=True, indexed=False)

    # whether or not this booking has been authorised
    is_authorised = ndb.BooleanProperty(indexed=False)

    def setFromInfo(self, info):
        self.reqid = info.reqid
        self.is_authorised = info.is_authorised

        self.requirements = []

        for requirement in info.requirements:
            self.requirements.append( BookingReq(reqname=requirement.reqname,
                                                 reqvalue=requirement.reqvalue) )

    def requirementsID(self):
        return self.key.integer_id()

    @classmethod
    def cancelBooking(cls, idnum, registry=DEFAULT_BOOKING_REGISTRY):
        """Cancel this booking - this deletes the requirements from the database"""
        k = ndb.Key(cls, int(idnum), parent=cls.ancestor(registry))
        k.delete()

    @classmethod
    def getQuery(cls, registry=DEFAULT_BOOKING_REGISTRY):
        return cls.query(ancestor=equipment_key(registry))

    @classmethod
    def ancestor(cls, registry=DEFAULT_BOOKING_REGISTRY):
        return equipment_key(registry)

class BookingReqsInfo:
    def __init__(self, reqs=None, reqs_id=None, registry=DEFAULT_BOOKING_REGISTRY):
        self.reqid = None
        self.requirements = []
        self.is_authorised = False

        self.reqs_id = None

        if reqs_id:
            self.reqs_id = reqs_id
            self._registry = registry
            self._CLASS = BookingReqs
            reqs = self._getFromDB()

            if not reqs:
                raise DataError("There are no requirements available with ID = '%s'" % reqs_id)

        if reqs:
            if reqs.reqid:
                self.reqid = int(reqs.reqid)

            if reqs.is_authorised:
                self.is_authorised = True

            if reqs.requirements:
                for requirement in reqs.requirements:
                    self.requirements.append( BookingReqInfo(requirement) )

            self._CLASS = BookingReqs
            self._registry = registry
            self.reqs_id = reqs.requirementsID()

    def _getKey(self):
        """Return the key for the datastore object that contains the data for this info"""
        if not self.reqs_id:
            return None

        return ndb.Key(self._CLASS, int(self.reqs_id), parent=self._CLASS.ancestor(self._registry))

    def _getFromDB(self):
        """Return the underlying datastore object that contains the data for this lab"""
        if not self.reqs_id:
            return None

        key = self._getKey()
        item = key.get()

        if not item:
            raise DataError("""There is a bug as the data for the Booking requirements object with ID='%s' seems to 
                               have disappeared from the data store!""" % (self.reqs_id),
                            detail=[str(key),str(self)])

        return item

    def equipmentRequirements(self):
        """Return the equipment requirements for this booking"""
        if self.reqid:
            return EquipmentReqsInfo(reqs_id=self.reqid, registry=DEFAULT_EQUIPMENT_REGISTRY)
        else:
            return None

class EquipmentType(ndb.Model):
    """The main model for representing a type of equipment (e.g. shaker)."""
    # The human readable name of the equipment
    name = ndb.StringProperty(indexed=False)
    # Human readable information about this type of equipment
    information = ndb.JsonProperty(indexed=False)
    # Booking requirements that are used as a template for all 
    # pieces of equipment of this type
    requirements = ndb.IntegerProperty(indexed=False)

    def setFromInfo(self, info):
        _db.setFromInfo(self, info)

        if info:
            requirements = info.requirements

    @classmethod
    def getQuery(cls, registry=DEFAULT_TYPES_REGISTRY):
        return cls.query(ancestor=types_key(registry))

    @classmethod
    def ancestor(cls, types_registry=DEFAULT_TYPES_REGISTRY):
        return types_key(types_registry)

class Equipment(ndb.Model):
    """The main model for representing an individual piece of equipment (e.g. Song's first shaker)."""
    # The human readable name of the equipment
    name = ndb.StringProperty(indexed=False)
    # IDString of the type of equipment
    equipment_type = ndb.StringProperty(indexed=True)
    # IDString of the lab in which this equipment is located
    laboratory = ndb.StringProperty(indexed=True)
    # The IDString for the calendar that manages the booking
    # for this piece of equipment
    calendar = ndb.StringProperty(indexed=False)
    # Information about the equipment as a dictionary that has been
    # serialised into a json string
    information = ndb.JsonProperty(indexed=False)
    # The requirements that must be provided by the user when making the booking
    requirements = ndb.IntegerProperty(indexed=False)
    # The booking constraints when trying to book this equipment
    constraints = ndb.StructuredProperty(BookingConstraint,indexed=False)

    def setFromInfo(self, info):
        _db.setFromInfo(self, info)
        self.equipment_type = info.equipment_type
        self.laboratory = info.laboratory
        self.calendar = info.calendar
        self.requirements = int(info.requirements)
        self.constraints = BookingConstraint.createFrom(info.constraints)

    @classmethod
    def getQuery(cls, registry=DEFAULT_EQUIPMENT_REGISTRY):
        return cls.query(ancestor=equipment_key(registry))

    @classmethod
    def ancestor(cls, equipment_registry=DEFAULT_EQUIPMENT_REGISTRY):
        return equipment_key(equipment_registry)

class Laboratory(ndb.Model):
    """The main model for representing an individual laboratory (that can
       contain lots of different pieces of equipment, but which has a single
       contact point and location"""
    # The human readable name of the laboratory
    name = ndb.StringProperty(indexed=False)
    # The location of the lab
    location = ndb.GeoPtProperty(indexed=False)
    # The email addresses of the contacts for this lab
    owners = ndb.StringProperty(indexed=False, repeated=True)
    # Information about this laboratory that is held as 
    # a dictionary that has been serialised to a json string
    information = ndb.JsonProperty(indexed=False)

    def setFromInfo(self, info):
        _db.setFromInfo(self, info)
        self.location = info.location
        self.owners = info.owners

    @classmethod
    def getQuery(cls, registry=DEFAULT_LABS_REGISTRY):
        return cls.query(ancestor=labs_key(registry))

    @classmethod
    def ancestor(cls, labs_registry=DEFAULT_LABS_REGISTRY):
        return labs_key(labs_registry)

class EquipmentACL(ndb.Model):
    """The main model for representing an access control rule
       for a piece of equipment"""
    # The ACL (integer)
    rule = ndb.IntegerProperty(indexed=True)
    # the user for which this rule applies
    user = ndb.ComputedProperty(lambda self: self.key.string_id())
    # the reason why this user has been assigned this rule
    reason = ndb.StringProperty(indexed=False)
    # any extra information about the rule, e.g. additional security levels
    information = ndb.JsonProperty(indexed=False)

    def setFromInfo(self, info):
        self.rule = info.rule
        self.reason = info.reason
        self.information = info.information

    def equipment(self):
        return self.key.parent().string_id()

    def email(self):
        return self.key.string_id()

    @classmethod
    def getQuery(cls, registry=DEFAULT_ACLS_REGISTRY):
        return cls.query(ancestor=acls_key(registry))

    @classmethod
    def getEquipmentQuery(cls, equipment_idstring, registry=DEFAULT_ACLS_REGISTRY):
        return cls.query(ancestor=ndb.Key(Equipment,equipment_idstring,parent=acls_key(registry)))

    @classmethod
    def ancestor(cls, registry=DEFAULT_ACLS_REGISTRY):
        return acls_key(registry)

    @classmethod
    def ancestorForEquipment(cls, equipment_idstring, registry=DEFAULT_ACLS_REGISTRY):
        return ndb.Key(Equipment,equipment_idstring,parent=acls_key(registry))

    @classmethod
    def banned(cls):
        return 0
    
    @classmethod
    def pending(cls):
        return 1

    @classmethod
    def authorised(cls):
        return 2

    @classmethod
    def administrator(cls):
        return 3


class BookingInfo:
    """Simple class that holds information about a booking"""
    def __init__(self, booking=None, equipment=None, booking_id=None, registry=DEFAULT_BOOKING_REGISTRY):
        self.equipment = None
        self.email = None
        self.project = None
        self.start_time = None
        self.end_time = None
        self.booking_time = None
        self.status = 0
        self.booking_id = None
        self.information = {}
        self._registry = None
        self.gcal_id = None
        self.requirements = None

        if equipment and booking_id:
            self._CLASS = Booking
            self._registry = registry
            self.equipment = equipment
            self.booking_id = int(booking_id)

            booking = self._getFromID()

        if booking:
            if booking.status:
                self.status = int(booking.status)

            if booking.start_time:
                self.start_time = booking.start_time

            if booking.end_time:
                self.end_time = booking.end_time

            if booking.booking_time:
                self.booking_time = booking.booking_time

            if booking.project:
                self.project = unicode(booking.project)

            if booking.information:
                self.information = booking.information

            if booking.gcal_id:
                self.gcal_id = booking.gcal_id

            if booking.requirements:
                self.requirements = int(booking.requirements)

            self.email = booking.email()
            self.equipment = booking.equipment()
            self.booking_id = booking.bookingID()

            self._CLASS = Booking
            self._registry = registry

    def _getKey(self):
        """Return the key for the data for this info"""
        if not (self.equipment and self.booking_id):
            return None
        else:
            return ndb.Key(self._CLASS, self.booking_id, 
                           parent=ndb.Key(Equipment, self.equipment, parent=bookings_key(self._registry)))

    def _getFromID(self):
        """Return the database booking for this info"""
        key = self._getKey()

        if key:
            item = key.get()
            if item:
                return item

        raise DataError("""There is a bug as the data for %s '%s-%s' seems to 
                           have disappeared from the data store!""" % (self._CLASS,self.equipment,self.booking_id),
                           detail=self)

    def toEvent(self):
        """Return this booking converted to a bsb.calendar.Event"""
        # get the name and initials of the person booking
        booking_account = accounts.get_account_by_email_unchecked(self.email)

        if not booking_account:
            raise BookingError("Cannot find the account for email '%s'" % self.email)

        equip = get_equipment(self.equipment)

        if not equip:
            raise BookingError("Cannot find the equipment matching ID string '%s'" % self.equipment)

        proj = projects.get_project_by_id(self.project)

        if not proj:
            raise BookingError("Cannot find the project that matches ID string '%s'" % self.project)

        summary = "%s | %s" % (booking_account.email, booking_account.initials)
        location = equip.getLaboratory().name
        desc = "Booked by %s. Project = %s" % (booking_account.name, proj.name)

        event = calendar.Event(self.start_time, self.end_time, summary, location, desc, self.gcal_id)

        return event

    def idString(self):
        """Return an ID string to identify this booking"""
        return "%s_%s" % (self.equipment,self.booking_id)

    def getProjectID(self):
        """Get the project ID assigned to this booking"""
        return self.project

    def getProjectName(self):
        """Return the name of the project associated with this booking"""
        mapping = projects.get_project_mapping()
        if self.project in mapping:
            return mapping[self.project]
        else:
            return "Unknown"

    def getEquipmentID(self):
        """Get the IDString of the equipment that has been booked"""
        return self.equipment

    def getEquipmentName(self):
        """Get the name of the equipment that has been booked"""
        mapping = get_equipment_mapping()
        if self.equipment in mapping:
            return mapping[self.equipment]
        else:
            return "Unknown"

    def getLaboratoryName(self):
        """Get the name of the laboratory in which the equipment has been booked"""
        mapping = get_laboratory_for_equipment_mapping()
        if self.equipment in mapping:
            return mapping[self.equipment][1]
        else:
            return "Unknown"

    def getLaboratoryID(self):
        """Get the IDString of the laboratory in which the equipment has been booked"""
        mapping = get_laboratory_for_equipment_mapping()
        if self.equipment in mapping:
            return mapping[self.equipment][0]
        else:
            return "unknown"

    def getTypeName(self):
        """Get the name of the equipment type for the equipment that has been booked"""
        mapping = get_type_for_equipment_mapping()
        if self.equipment in mapping:
            return mapping[self.equipment][1]
        else:
            return "Unknown"

    def getTypeID(self):
        """Get the IDString of the equipment type for the equipment that has been booked"""
        mapping = get_type_for_equipment_mapping()
        if self.equipment in mapping:
            return mapping[self.equipment][0]
        else:
            return "unknown"

    def getEquipment(self, registry=DEFAULT_EQUIPMENT_REGISTRY):
        """Return the piece of equipment managed by this booking"""
        return get_equipment(self.equipment, registry)

    def getRequirements(self, registry=DEFAULT_BOOKING_REGISTRY):
        """Return the user-supplied requirements associated with this booking.
           If no requirements are needed, then this returns None"""
        if self.requirements:
            # Note that booking requirements are stored in the DEFAULT_EQUIPMENT_REGISTRY
            return BookingReqsInfo( reqs_id=self.requirements, registry=registry )
        else:
            return None

    def getAccount(self, account):
        """Return the account associated with the user who made this booking"""
        if account.email == self.user:
            return account
        else:
            return accounts.get_account_by_email(account, self.user)

    def getProject(self):
        """Return the project to which this booking has been assigned"""
        return projects.get_project_by_id(self.information["project"])

    @classmethod
    def _timeToString(cls, time, isoformat=False):
        if not time:
            return None
        elif isoformat:
            return time.isoformat()
        else:
            return time.strftime("%d:%m:%y %H-%M")
            
    def getStartTime(self, isoformat=False):
        """Return a string for the start time of the booking. This will be in
          an isoformat if isoformat is True, otherwise it will be in a pretty format."""
        return _timeToString(self.start_time, isoformat)

    def getEndTime(self, isoformat=False):
        """Return a string for the end time of the booking. This will be in
           an isoformat if isoformat is True, otherwise it will be in a pretty format."""
        return _timeToString(self.end_time, isoformat)

    def isCancelled(self):
        """Return whether or not this booking has been cancelled"""
        return self.status == Booking.cancelled()

    def isReserved(self):
        """Return whether or not we have reserved the booking (but not confirmed)"""
        return self.status == Booking.reserved()

    def isConfirmed(self):
        """Return whether or not this booking has been confirmed"""
        return self.status == Booking.confirmed()

    def isPendingAuthorisation(self):
        """Return whether or not this booking is pending authorisation"""
        return self.isCurrentOrFuture() and self.status == Booking.pendingAuthorisation()

    def isDeniedAuthorisation(self):
        """Return whether or not this booking is denied authorisation"""
        return self.status == Booking.deniedAuthorisation()

    def isPast(self):
        """Return whether or not this booking is in the past"""
        return self.end_time < get_now_time()

    def isCurrentOrFuture(self):
        """Return whether or not this booking is either current or in the future"""
        return self.end_time > get_now_time()

    def isActive(self):
        """Return whether or not this booking is currently active
           (i.e. is running now)"""
        if self.status == Booking.confirmed():
            now_time = get_now_time()
            return (now_time >= self.start_time) and (now_time <= self.end_time)
        else:
            return False

    def isOwner(self, account):
        """Return whether or not this booking is owned by the passed account"""
        return self.email == account.email

    def __str__(self):
        """Return a string representation of this booking"""
        return "Booking( user='%s', equipment='%s', booking_id='%s', start_time='%s', end_time='%s' )" % \
                      (self.email, self.getEquipment(), self.booking_id, 
                       BookingInfo._timeToString(self.start_time),
                       BookingInfo._timeToString(self.end_time))

    @classmethod
    def _describeBookings(cls, bookings):
        message = []

        for booking in bookings:
            if booking.isConfirmed():
                message.append( "%s [%s until %s]" % (booking.email, 
                                                      BookingInfo._timeToString(booking.start_time),
                                                      BookingInfo._timeToString(booking.end_time)) )
            else:
                message.append( "%s [%s until %s - NOT CONFIRMED YET]" % (booking.email, 
                                                      BookingInfo._timeToString(booking.start_time),
                                                      BookingInfo._timeToString(booking.end_time)) )

        return ", ".join(message)

    @classmethod
    def create(cls, equipment, account, start_time, end_time, registry=DEFAULT_BOOKING_REGISTRY):
        """Create a reservation for the equipment 'equipment', for the passed user and time.
           This will guarantee that the reservation is unique"""
        
        # get the parent key
        parent_key = ndb.Key(Equipment, equipment.idstring, parent=bookings_key(registry))

        # get a new ID from the datastore
        new_id = ndb.Model.allocate_ids(size = 1, parent = parent_key)[0]

        # create a reservation and place it into the database
        my_booking = Booking()
        my_booking.key = ndb.Key(Booking, new_id, parent=parent_key)
        my_booking.start_time = start_time
        my_booking.end_time = end_time
        my_booking.booking_time = get_now_time()
        my_booking.user = account.email
        my_booking.status = Booking.reserved()

        my_booking.put()

        # now see whether or not this reservation clashes with anyone else...
        bookings = Booking.getEquipmentQuery(equipment.idstring,registry) \
                          .filter(Booking.end_time > start_time).fetch()
        clashing_bookings = []

        for booking in bookings:
            if booking.key != my_booking.key:
                if booking.start_time < end_time:
                    # we have a clash - is this booking confirmed?
                    if booking.status == Booking.confirmed():
                        clashing_bookings.append( BookingInfo(booking) )
                    elif booking.status == Booking.reserved():
                        # we are both trying to book at once. The winner is the person
                        # who booked first...
                        if booking.booking_time < my_booking.booking_time:
                            clashing_bookings.append( BookingInfo(booking) )
                        elif booking.booking_time == my_booking.booking_time:
                            # we booked at the same time - the winner is the one with the alphabetically
                            # later email address
                            if booking.user < my_booking.user:
                                booking.status = Booking.cancelled()
                                booking.put()
                            else:
                                clashing_bookings.append( BookingInfo(booking) )
                        else:
                            # we have won - automatically cancel the other booking
                            booking.status = Booking.cancelled()
                            booking.put()

        if len(clashing_bookings) > 0:
            # we cannot get a unique booking
            my_booking.key.delete()
            raise BookingError("""Cannot create a reservation for this time as someone else has already
                                  created a booking. '%s'""" % cls._describeBookings(clashing_bookings),
                                  detail=clashing_bookings)

        return BookingInfo(my_booking)


class EquipmentACLInfo:
    """Simple class that holds the equipment ACL"""
    def __init__(self, acl=None, registry=DEFAULT_ACLS_REGISTRY):
        self.equipment = None
        self.email = None
        self.rule = 0
        self.reason = None
        self.information = {}
        self._registry = None

        if acl:
            if acl.rule:
                 self.rule = int(acl.rule)

            if acl.reason:
                 self.reason = unicode(acl.reason)

            if acl.information:
                 self.information = acl.information

            self.email = acl.email()
            self.equipment = acl.equipment()

            self._CLASS = EquipmentACL
            self._registry = registry

    def isValid(self):
        """Return whether this ACL is valid and points to an existing piece of equipment"""
        if get_equipment(self.equipment):
            return True
        else:
            return False

    def assertValid(self, account, equipment=None):
        """Assert that the passed ACL gives access for the passed user to 
           the passed piece of equipment"""

        if account.email == self.email and ((not equipment) or equipment.idstring == self.equipment):
            if account.is_approved and self.isAuthorised():
                return

        raise PermissionError("""There is a problem using accessing equipment '%s' using account '%s'.""" \
                                   (equipment.idstring,account.email), detail={"acl":self, "account":account})

    def assertIsAdministrator(self, account, equipment=None):
        """Assert that the passed ACL gives admin access for the passed user
           to the passed piece of equipment"""

        if account.email == self.email and ((not equipment) or equipment.idstring == self.equipment):
            if account.is_approved and self.isAdministrator():
                return

        raise PermissionError("""There is a problem using accessing equipment '%s' using account '%s'.""" \
                                   (equipment.idstring,account.email), detail={"acl":self, "account":account})

    @classmethod
    def getRulesForAccount(cls, account, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the access rules for this user account"""
        if not account:
            return None

        items = EquipmentACL.getQuery(registry).filter(EquipmentACL.user == account.email).fetch()

        if items:
            rules = []
            for item in items:
                acl = EquipmentACLInfo(item)
                if acl.isValid():
                    rules.append(acl)

            return rules
        else:
            return None

    @classmethod
    def getRulesForEquipment(cls, account, equipment, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the access rules for the passed piece of equipment"""
        if not equipment:
            return None

        if not cls.isAuthorisedAccount(account, equipment, registry):
            return None

        items = EquipmentACL.getEquipmentQuery(equipment.idstring,registry).fetch()

        if items:
            rules = []
            for item in items:
                rules.append( EquipmentACLInfo(item) )

            return rules
        else:
            return None

    @classmethod
    def getRule(cls, account, equipment, registry=DEFAULT_ACLS_REGISTRY):
        """Return the access rule for the passed piece of equipment"""
        if not account or not equipment:
            return None

        key = ndb.Key(Equipment, equipment.idstring, EquipmentACL, account.email,
                      parent=acls_key(registry))

        item = key.get()

        if item:
            return EquipmentACLInfo(item)
        else:
            return None

    @classmethod
    def _getEquipmentFromRules(cls, items):
        if not items:
            return None

        equipment = []
        for item in items:
            equip = item.equipment()
            if equip:
                equipment.append(equip)

        if len(equipment) > 0:
            return equipment
        else:
            return None

    @classmethod
    def _getEmailsFromRules(cls, items, include_reasons=False):
        if not items:
            return None

        emails = []
        for item in items:
            email = item.email()
            if email:
                if include_reasons:
                    emails.append( (email,item.reason) )
                else:
                    emails.append(email)
        
        if len(emails) > 0:
            return emails
        else:
            return None

    @classmethod
    def getAuthorisedEquipment(cls, account, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the equipment idstrings that this account is authorised to use"""
        if not account:
            return None

        elif not account.is_approved:
            return None

        items = EquipmentACL.getQuery(registry).filter(EquipmentACL.user == account.email)\
                                               .filter(EquipmentACL.rule >= EquipmentACL.authorised()).fetch()

        return cls._getEquipmentFromRules(items)

    @classmethod
    def getAdministeredEquipment(cls, account, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the equipment idstrings for which this account is an administrator"""
        if not account:
            return None

        elif not account.is_approved:
            return None

        items = EquipmentACL.getQuery(registry).filter(EquipmentACL.user == account.email)\
                                               .filter(EquipmentACL.rule == EquipmentACL.administrator()).fetch()

        return cls._getEquipmentFromRules(items)

    @classmethod
    def getPendingEquipment(cls, account, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the equipment idstrings that this account is awaiting authorisation to use"""
        if not account:
            return None

        elif not account.is_approved:
            return None

        items = EquipmentACL.getQuery(registry).filter(EquipmentACL.user == account.email)\
                                               .filter(EquipmentACL.rule == EquipmentACL.pending()).fetch()

        return cls._getEquipmentFromRules(items)

    @classmethod
    def getBannedEquipment(cls, account, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the equipment idstrings that this account is banned from using"""
        if not account:
            return None

        elif not account.is_approved:
            return None

        items = EquipmentACL.getQuery(registry).filter(EquipmentACL.user == account.email)\
                                               .filter(EquipmentACL.rule == EquipmentACL.banned()).fetch()

        return cls._getEquipmentFromRules(items)

    @classmethod
    def getAuthorisedUsers(cls, account, equipment, include_reasons=False, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the emails of users who are authorised to use 'equipment'. Note that
           only administrators of this equipment can see this list"""
        if not cls.isAuthorisedAccount(account, equipment, registry):
            return None

        items = EquipmentACL.getEquipmentQuery(equipment.idstring,registry)\
                            .filter(EquipmentACL.rule >= EquipmentACL.authorised()).fetch()

        return cls._getEmailsFromRules(items,include_reasons)

    @classmethod
    def getAdministratorUsers(cls, account, equipment, include_reasons=False, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the emails of users who are administrators of 'equipment'. Note that
           only administrators of this equipment can see this list"""
        if not cls.isAuthorisedAccount(account, equipment, registry):
            return None

        items = EquipmentACL.getEquipmentQuery(equipment.idstring,registry)\
                            .filter(EquipmentACL.rule == EquipmentACL.administrator()).fetch()

        return cls._getEmailsFromRules(items,include_reasons)

    @classmethod
    def getPendingUsers(cls, account, equipment, include_reasons=False, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the emails of users who are awaiting authorisation to use 'equipment'. Note that
           only administrators of this equipment can see this list"""
        if not cls.isAuthorisedAccount(account, equipment, registry):
            return None

        items = EquipmentACL.getEquipmentQuery(equipment.idstring,registry)\
                            .filter(EquipmentACL.rule == EquipmentACL.pending()).fetch()

        return cls._getEmailsFromRules(items,include_reasons)

    @classmethod
    def getBannedUsers(cls, account, equipment, include_reasons=False, registry=DEFAULT_ACLS_REGISTRY):
        """Return all of the emails of users who are banned from using 'equipment'. Note that
           only administrators of this equipment can see this list"""
        if not cls.isAuthorisedAccount(account, equipment, registry):
            return None

        items = EquipmentACL.getEquipmentQuery(equipment.idstring,registry)\
                            .filter(EquipmentACL.rule == EquipmentACL.banned()).fetch()

        return cls._getEmailsFromRules(items,include_reasons)

    @classmethod
    def isAuthorisedAccount(cls, account, equipment, registry=DEFAULT_ACLS_REGISTRY):
        """Return whether or not the passed account is an admin account for the passed equipment"""
        if not account.is_approved:
            return False

        elif account.is_admin:
            return True

        rule = cls.getRule(account, equipment, registry)

        if not rule:
            return False
        else:
            return rule.isAdmin()

    @classmethod
    def _assertValidRule(cls, rule):
        rule = int(rule)
        if rule < 0 or rule > EquipmentACL.administrator():
            raise InputError("Invalid ACL rule '%s'" % rule)
        return rule

    @classmethod
    def setRule(cls, account, equipment, email, rule, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """As the user 'account' add the rule 'rule' to the piece of equipment 'equipment' 
           for the user with email 'email'"""
        email = to_email(email)

        if account is None or equipment is None or email is None:
            return

        # email must be of a user who are authorised with this system
        account_mapping = accounts.get_account_mapping()

        if not email in account_mapping:
            raise accounts.MissingAccountError("There is no user registered with email '%s'" % email)

        rule = cls._assertValidRule(rule)

        if rule == EquipmentACL.pending() and account.email == email:
            # user is requesting access
            if not account.is_approved:
                raise PermissionError("""Cannot set the rule for email '%s' to equipment '%s' as your account '%s' has 
                                         not been approved. Only administrator accounts, or registered administrators
                                         for this piece of equipment can set permission rules.""" % \
                                      (email, equipment.name, account.email))

        elif not cls.isAuthorisedAccount(account, equipment, registry):
            raise PermissionError("""Cannot set the rule for email '%s' to equipment '%s' as your account '%s' does 
                                     not have permission. Only administrator accounts, or registered administrators
                                     for this piece of equipment can set permission rules.""" % \
                                      (email, equipment.name, account.email))

        key = ndb.Key('Equipment', equipment.idstring, EquipmentACL, email,
                       parent=acls_key(DEFAULT_ACLS_REGISTRY))

        item = key.get()

        if not item:
            item = EquipmentACL()
            item.key = key

        item.reason = reason
        item.rule = rule
        item.put()

    @classmethod
    def setBanned(cls, account, equipment, email, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """As the user 'account' set the rule for user with email 'email' to 'banned'
           for the passed piece of equipment"""
        cls.setRule(account, equipment, email, EquipmentACL.banned(), reason, registry)

    @classmethod
    def setPending(cls, account, equipment, email, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """As the user 'account' set the rule for user with email 'email' to 'pending'
           for the passed piece of equipment"""
        cls.setRule(account, equipment, email, EquipmentACL.pending(), reason, registry)

    @classmethod
    def setAuthorised(cls, account, equipment, email, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """As the user 'account' set the rule for user with email 'email' to 'authorised'
           for the passed piece of equipment"""
        cls.setRule(account, equipment, email, EquipmentACL.authorised(), reason, registry)

    @classmethod
    def setAdministrator(cls, account, equipment, email, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """As the user 'account' set the rule for user with email 'email' to 'administrator'
           for the passed piece of equipment"""
        cls.setRule(account, equipment, email, EquipmentACL.administrator(), reason, registry)

    @classmethod
    def setUsersWithRule(cls, account, equipment, emails, rule, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """Set the list of users with rule 'rule' to 'emails'"""
        rule = cls._assertValidRule(rule)

        if not cls.isAuthorisedAccount(account, equipment, registry):
            raise PermissionError("""Cannot set the rule for emails '%s' to equipment '%s' as your account '%s' does 
                                     not have permission. Only administrator accounts, or registered administrators
                                     for this piece of equipment can set permission rules.""" % \
                                      (emails, equipment.name, account.email))

        # now clean the list of emails - emails must be of users who are authorised with this system
        account_mapping = accounts.get_account_mapping()

        clean_emails = []
        missing_accounts = []
        for email in emails:
            email = to_email(email)
            if email:
                if email in account_mapping:
                    clean_emails.append(email)
                else:
                    missing_accounts.append(email)

        emails = clean_emails

        # get all of the existing users at this level for this piece of equipment
        items = EquipmentACL.getEquipmentQuery(equipment.idstring,registry)\
                            .filter(EquipmentACL.rule == rule).fetch()

        put_items = []
        del_keys = []

        current_emails = []
        
        for item in items:
            if not (item.email() in emails):
                # we need to remove this rule
                if rule == EquipmentACL.administrator():
                    # drop this user down to authorised
                    item.rule = EquipmentACL.authorised()
                    item.reason = reason
                    put_items.append(item)
                elif item.rule != EquipmentACL.banned():
                    # drop this user down to banned
                    item.rule = EquipmentACL.banned()
                    item.reason = reason
                    put_items.append(item)
                else:
                    # just delete this user
                    del_keys.append(item.key)
            else:
                current_emails.append(item.email())

        for email in emails:
            if not (email in current_emails):
                # we need to add this email
                key = ndb.Key( 'Equipment', equipment.idstring, 'EquipmentACL', email, parent=acls_key(registry) )
                item = key.get()

                if item:
                    if not (item.rule == EquipmentACL.administrator() and rule == EquipmentACL.authorised()):
                        item.rule = rule
                        item.reason = reason
                        put_items.append(item)
                else:
                    item = EquipmentACL()
                    item.rule = rule
                    item.reason = reason
                    item.key = key
                    put_items.append(item)

        ndb.delete_multi(del_keys)
        ndb.put_multi(put_items)

        if len(missing_accounts) > 0:
            raise accounts.MissingAccountError("Some emails are not recognised as belonging to registered users of this system: [ %s ]" \
                                                     % (", ".join(missing_accounts)) )

    @classmethod
    def setBannedUsers(cls, account, equipment, emails, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """Set the list of banned users for this piece of equipment to 'emails'"""
        EquipmentACLInfo.setUsersWithRule(account, equipment, emails, EquipmentACL.banned(), reason, registry)

    @classmethod
    def setPendingUsers(cls, account, equipment, emails, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """Set the list of pending users for this piece of equipment to 'emails'"""
        EquipmentACLInfo.setUsersWithRule(account, equipment, emails, EquipmentACL.pending(), reason, registry)

    @classmethod
    def setAuthorisedUsers(cls, account, equipment, emails, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """Set the list of authorised users for this piece of equipment to 'emails'"""
        EquipmentACLInfo.setUsersWithRule(account, equipment, emails, EquipmentACL.authorised(), reason, registry)

    @classmethod
    def setAdministratorUsers(cls, account, equipment, emails, reason=None, registry=DEFAULT_ACLS_REGISTRY):
        """Set the list of banned users for this piece of equipment to 'emails'"""
        EquipmentACLInfo.setUsersWithRule(account, equipment, emails, EquipmentACL.administrator(), reason, registry)

    def isBanned(self):
        return self.rule == EquipmentACL.banned()

    def isPending(self):
        return self.rule == EquipmentACL.pending()

    def isAuthorised(self):
        return self.rule == EquipmentACL.authorised() or self.rule == EquipmentACL.administrator()

    def isAdministrator(self):
        return self.rule == EquipmentACL.administrator()

    def isAdmin(self):
        return self.isAdministrator()

class EquipmentTypeInfo(_db.StandardInfo):
    """Simple class that holds the information about each equipment type"""
    def __init__(self, typ=None, registry=DEFAULT_TYPES_REGISTRY):
        _db.StandardInfo.__init__(self, typ, registry)
        self.requirements = None

        if typ:
            if typ.requirements:
                self.requirements = int(typ.requirements)

    def getRequirements(self, registry=None):
        """Return the booking requirements used for equipment of this type.
           This is a template that can be modifed by each individual piece 
           of equipment"""
        if self.requirements:
            return EquipmentReqsInfo( reqs_id=self.requirements, registry=registry )
        else:
            return None

    @classmethod
    def getAll(cls, account, registry=None):
        """Return all of the items in the database"""
        return _db.getAllFromDB(account, EquipmentType, registry)

    @classmethod
    def backup(cls, account, registry=None):
        """Return a string containing the entire database in pickled form"""
        return _db.backup(account, cls, EquipmentType, registry)

    @classmethod
    def restore(cls, account, data, registry=None):
        """Restore the database from the passed 'data' string containing a pickle of all of the objects"""
        _db.restore(account, cls, EquipmentType, registry)

    @classmethod
    def deleteDB(cls, account, registry=None):
        """Delete the entire database"""
        _db.deleteDB(account, cls, EquipmentType, registry)

class LaboratoryInfo(_db.StandardInfo):
    """Simple class that holds the information about each laboratory"""
    def __init__(self, lab=None, registry=DEFAULT_LABS_REGISTRY):
        _db.StandardInfo.__init__(self, lab, registry)
        self.location = None
        self.owners = []

        if lab:
            if lab.location:
                self.location = lab.location

            for owner in lab.owners:
                self.owners.append( unicode(owner) )

    @classmethod
    def getAll(cls, account, registry=None):
        """Return all of the items in the database"""
        return _db.getAllFromDB(account, Laboratory, registry)

    @classmethod
    def backup(cls, account, registry=None):
        """Return a string containing the entire database in pickled form"""
        return _db.backup(account, cls, Laboratory, registry)

    @classmethod
    def restore(cls, account, data, registry=None):
        """Restore the database from the passed 'data' string containing a pickle of all of the objects"""
        _db.restore(account, cls, Laboratory, data, registry)

    @classmethod
    def deleteDB(cls, account, registry=None):
        """Delete the entire database"""
        _db.deleteDB(account, cls, Laboratory, registry)

    def _getLab(self):
        """Return the underlying datastore object that contains the data for this lab"""
        return self._getFromDB()

    def setLocation(self, account, location):
        """Function called to set the location of the lab to 'location'. The 
           passed location should be a GeoPt or compatible with a GeoPt"""

        assert_is_admin(account, "Only administrator accounts can change the location of a lab")

        if location != self.location:
            lab = self._getLab()

            try:
                lab.location = location
                lab.put()
                self.location = location
            except Exception as e:
                raise InputError("""Cannot set the location of lab '%s' to '%s'.
                                    Click below for more details.""" % (lab.name, location),
                                 detail=e)

    def setOwners(self, account, owners):
        """Function called to set the owners of the lab to 'owners'. This should
           be a list of valid email addresses"""
        if self.idstring is None:
            return

        assert_is_admin(account, "Only administrator accounts can change the owner of a lab")

        invalid_owners = []
        new_owners = []

        for owner in owners:
            try:
                owner = owner.lstrip().rstrip()

                if len(owner) > 0:
                    if re.match(r"[^@]+@[^@]+\.[^@]+", owner):
                        # this looks like a valid email address
                        new_owners.append(owner)
                    else:
                        invalid_owners.append( unicode(owner) )
            except:
                invalid_owners.append( unicode(owner) )

        if len(invalid_owners) > 0:
            raise InputError("""Cannot update the owners of laboratory '%s' as the list
                                of email addresses contains some invalid emails [ %s ].""" % \
                                   (self.name, ", ".join(invalid_owners)), detail=owners)

        # the list of emails is ok, so update if changed
        if not lists_equal(self.owners, new_owners):
            lab = self._getLab()
            lab.owners = new_owners
            lab.put()

            self.owners = new_owners

def get_equipment_type(idstring, registry=DEFAULT_TYPES_REGISTRY):
    """Return the equipment type matching the IDString 'idstring')"""
    return _db.get_item(EquipmentType, EquipmentTypeInfo, idstring, registry)

def get_laboratory(idstring, registry=DEFAULT_LABS_REGISTRY):
    """Return the laboratory matching the IDString 'idstring'"""
    return _db.get_item(Laboratory, LaboratoryInfo, idstring, registry)

class EquipmentInfo(_db.StandardInfo):
    """Simple class that holds the information about each piece of equipment"""
    def __init__(self, equip=None, registry=DEFAULT_EQUIPMENT_REGISTRY):
        _db.StandardInfo.__init__(self, equip, registry)
        self.equipment_type = None
        self.laboratory = None
        self.calendar = None
        self.requirements = None
        self.constraints = None

        if equip:
            if equip.equipment_type:
                self.equipment_type = unicode(equip.equipment_type)

            if equip.laboratory:
                self.laboratory = unicode(equip.laboratory)

            if equip.calendar:
                self.calendar = unicode(equip.calendar)

            if equip.requirements:
                self.requirements = int(equip.requirements)

            if equip.constraints:
                self.constraints = BookingConstraintInfo(equip.constraints)

    @classmethod
    def getAll(cls, account, registry=None):
        """Return all of the items in the database"""
        return _db.getAllFromDB(account, Equipment, registry)

    @classmethod
    def backup(cls, account, registry=None):
        """Return a string containing the entire database in pickled form"""
        return _db.backup(account, cls, Equipment, registry)

    @classmethod
    def restore(cls, account, data, registry=None):
        """Restore the database from the passed 'data' string containing a pickle of all of the objects"""
        _db.restore(account, cls, Equipment, data, registry)

    @classmethod
    def deleteDB(cls, account, registry=None):
        """Delete the entire database"""
        _db.deleteDB(account, cls, Equipment, registry)
 
    def getLaboratoryID(self):
        """Return the IDString for the laboratory"""
        return self.laboratory

    def getEquipmentTypeID(self):
        """Return the IDString for the laboratory"""
        return self.equipment_type

    def getLaboratoryName(self):
        """Return the name for the laboratory from the memcache"""
        return get_laboratory_mapping()[self.laboratory]

    def getEquipmentTypeName(self):
        """Return the name for the equipment type from the memcache"""
        return get_equipment_type_mapping()[self.equipment_type]

    def getLaboratory(self):
        """Return the laboratory in which this equipment is located"""
        return get_laboratory(self.laboratory)

    def getEquipmentType(self):
        """Return the equipment type for this piece of equipment"""
        return get_equipment_type(self.equipment_type)

    def getFullName(self):
        """Return a human readable string describing this piece of equipment"""
        return "%s | %s | %s" % (self.getLaboratoryName(),self.getEquipmentTypeName(),self.name)

    def getACLs(self, account):
        """Return the ACL rules associated with this piece of equipment"""
        return EquipmentACLInfo.getRulesForEquipment(account, self)

    def getACL(self, account):
        """Return the ACL rule for this piece of equipment for this user"""
        return EquipmentACLInfo.getRule(account, self)

    def getBannedUsers(self, account, include_reasons=False):
        """Return a list of banned users for this piece of equipment"""
        return EquipmentACLInfo.getBannedUsers(account, self, include_reasons)

    def getPendingUsers(self, account, include_reasons=False):
        """Return the list of pending users for this piece of equipment"""
        return EquipmentACLInfo.getPendingUsers(account, self, include_reasons)

    def getAuthorisedUsers(self, account, include_reasons=False):
        """Return the list of authorised users for this piece of equipment"""
        return EquipmentACLInfo.getAuthorisedUsers(account, self, include_reasons)

    def setBannedUsers(self, account, emails, reason=None):
        """Set the list of banned users for this piece of equipment to 'emails'"""
        EquipmentACLInfo.setBannedUsers(account, self, emails, reason)
        self._updateCalendarPermissions(account)

    def setPendingUsers(self, account, emails, reason=None):
        """Set the list of pending users for this piece of equipment to 'emails'"""
        EquipmentACLInfo.setPendingUsers(account, self, emails, reason)
        self._updateCalendarPermissions(account)

    def setAuthorisedUsers(self, account, emails, reason=None):
        """Set the list of authorised users for this piece of equipment to 'emails'"""
        EquipmentACLInfo.setAuthorisedUsers(account, self, emails, reason)
        self._updateCalendarPermissions(account)

    def setAdministratorUsers(self, account, emails, reason=None):
        """Set the list of banned users for this piece of equipment to 'emails'"""
        EquipmentACLInfo.setAdministratorUsers(account, self, emails, reason)
        self._updateCalendarPermissions(account)

    def getAdministratorUsers(self, account, include_reasons=False):
        """Return the list of administrator users for this piece of equipment"""
        return EquipmentACLInfo.getAdministratorUsers(account, self, include_reasons)

    def setUserIsBanned(self, account, email, reason=None):
        """Set that the user with email 'email' is banned from using this piece of equipment"""
        EquipmentACLInfo.setBanned(account, self, email, reason)
        self._updateCalendarPermissions(account)

    def setUserIsPending(self, account, email, reason=None):
        """Set that the user with email 'email' is pending use of this piece of equipment"""
        EquipmentACLInfo.setPending(account, self, email, reason)
        self._updateCalendarPermissions(account)

    def setUserIsAuthorised(self, account, email, reason=None):
        """Set that the user with email 'email' is authorised to use this piece of equipment"""
        EquipmentACLInfo.setAuthorised(account, self, email, reason)
        self._updateCalendarPermissions(account)

    def setUserIsAdministrator(self, account, email, reason=None):
        """Set that the user with email 'email' is an administrator of this piece of equipment"""
        EquipmentACLInfo.setAdministrator(account, self, email, reason)
        self._updateCalendarPermissions(account)

    def _updateCalendarPermissions(self, account):
        """Update who can view the calendar based on the list of authorised users of this
           equipment. This should be called whenever the list of authorised users of this 
           equipment changes"""
        calendar = self.getCalendar(account)

        if calendar:
            calendar.setViewers(account, self.getAuthorisedUsers(account))

    def getCalendar(self, account):
        """Return the calendar for this piece of equipment"""
        return calendar.get_calendar(account, self.calendar)

    def createCalendar(self, account):
        """Function used to create the calendar for this piece of equipment"""
        if self.calendar:
            cal = calendar.get_calendar(account, self.calendar)

            if cal:
               return cal 

        # we need to create a calendar for this item and then save the name
        # We will use the name lab.equipment_type.equipment_name, using the IDStrings
        cal_name = "%s.%s.%s" % (self.laboratory,self.equipment_type,name_to_idstring(self.name))

        try:
            cal = calendar.add_calendar(account, cal_name)

        except calendar.DuplicateCalendarError:
            # we have already made this calendar :-)
            cal = calendar.get_calendar_by_name(account, name)

        if cal:
            self.calendar = cal.idstring
            item = self._getFromDB()
            if item:
                item.calendar = cal.idstring
                item.put()
        else:
            raise calendar.ConnectionError("""Failed to create the calendar '%s' for equipment item '%s'""" % \
                            (cal_name,self.name), detail=self)

        return cal

    def makeReservation(self, account, acl, start_time, end_time, is_demo=False):
        """Call this function to try to reserve use of this piece of equipment
           from 'start_time' until 'end_time'. You must pass in your
           account and a valid ACL for this piece of equipment"""
        acl.assertValid(account, self)

        # first validate that the times don't violate any of the constraints
        if self.constraints:
            (start_time, end_time) = self.constraints.validate(start_time, end_time)

        # ensure we start before we finish!
        if start_time > end_time:
            tmp = start_time
            start_time = end_time
            end_time = tmp

        if start_time == end_time:
            raise BookingError("Could not create a reservation as the start time (%s) equals the end time (%s)" % \
                                 (to_string(start_time),to_string(end_time)))
        
        now_time = get_now_time()

        if start_time < now_time:
            raise BookingError("Could not create a reservation as the start time (%s) is in the past (now is %s)" % \
                                 (to_string(start_time),to_string(now_time)))

        if not is_demo:
            # try to create a new booking object that exists in the time for this 
            # booking
            my_booking = BookingInfo.create(self, account, start_time, end_time)

            if not my_booking:
                raise BookingError("Could not create the booking!")

            return my_booking

    def _getBooking(self, account, acl, reservation):
        acl.assertValid(account, self)

        key = ndb.Key(Equipment, self.idstring, Booking, int(reservation),
                      parent=bookings_key(DEFAULT_BOOKING_REGISTRY))

        return key.get()

    def getBooking(self, account, acl, reservation):
        """Return the reservation associated with this equipment with ID 'reservation'"""
        b = self._getBooking(account, acl, reservation)

        if b:
            return BookingInfo(b)
        else:
            return None

    def confirmBooking(self, account, acl, reservation, project, booking_reqs=None):
        """Call this function to confirm the booking associated with the passed
           reservation ID, adding in the necessary extra booking requirements associated
           with the booking (if necessary)"""

        booking = self._getBooking(account, acl, reservation)

        if not booking:
            raise BookingError("There is no booking associated with booking ID '%s'" % reservation)

        if booking.status != Booking.reserved():
            raise BookingError("You cannot confirm a booking that is not in the 'reserved' state.",
                               detail=BookingInfo(booking))

        if booking_reqs:
            booking.requirements = booking_reqs.reqs_id

        booking.project = to_string(project)

        item_reqs = self.getRequirements()

        if item_reqs and item_reqs.needs_authorisation:
            booking.status = Booking.pendingAuthorisation()
        else:
            booking.status = Booking.confirmed()

        # Add the event to the google calendar so that it is visible
        event = self.getCalendar(account).addEvent(account, BookingInfo(booking).toEvent())

        if event:
            booking.gcal_id = event.gcal_id

        booking.put()

        return BookingInfo(booking)

    def cancelBooking(self, account, acl, reservation):
        """Call this function to cancel the booking associated with the
           passed reservation ID"""

        booking = self._getBooking(account, acl, reservation)

        if not booking:
            raise BookingError("There is no booking associated with booking ID '%s' to cancel!" % reservation)

        # we cannot cancel confirmed bookings that are in the past
        if booking.status == Booking.confirmed() or booking.status == Booking.pendingAuthorisation():
            is_confirmed = True
            now_time = get_now_time()

            if booking.end_time <= now_time:
                raise BookingError("You cannot cancel booking '%s' as it is in the past." % reservation,
                                   detail = BookingInfo(booking))
            
            if booking.start_time <= now_time:
                # we can modify the booking to cancel the remaining time
                booking.end_time = now_time
                event = self.getCalendar(account).updateEvent(account, BookingInfo(booking).toEvent())

                if event:
                    booking.gcal_id = event.gcal_id
                    booking.put()
                    return "The time remaining on the booking has been cancelled"

            # remove this booking from the calendar
            self.getCalendar(account).removeEvent(account, BookingInfo(booking).toEvent())
            booking.gcal_id = None
        else:
            is_confirmed = False

        # cancel this booking
        booking.status = booking.cancelled()
        booking.put()

        if is_confirmed:
            return "The booking has been cancelled"
        else:
            return "The reservation has been cancelled"

    def denyBooking(self, account, acl, reservation, reason):
        """Deny the booking with the passed reservation, providing the reason why"""
        acl.assertIsAdministrator(account, self)

        booking = self._getBooking(account, acl, reservation)

        if not booking:
            raise BookingError("There is no booking associated with booking ID '%s' to deny!" % reservation)

        # we cannot deny confirmed bookings that are in the past
        if booking.status in [Booking.reserved(), Booking.confirmed(), Booking.pendingAuthorisation()]:
            now_time = get_now_time()

            if booking.end_time <= now_time:
                raise BookingError("You cannot deny booking '%s' as it is in the past." % reservation,
                                   detail = BookingInfo(booking))

            # remove this booking from the calendar
            self.getCalendar(account).removeEvent(account, BookingInfo(booking).toEvent())
            booking.gcal_id = None
            booking.status = Booking.deniedAuthorisation()       
            booking.setInformation("denied_reason", reason)
            booking.put()

    def allowBooking(self, account, acl, reservation):
        """Authorise the booking with the passed reservation"""
        acl.assertIsAdministrator(account, self)

        booking = self._getBooking(account, acl, reservation)

        if not booking:
            raise BookingError("There is no booking associated with booking ID '%s' to authorise!" % reservation)

        # we cannot authorised confirmed bookings that are in the past
        if booking.status == Booking.pendingAuthorisation():
            now_time = get_now_time()

            if booking.end_time <= now_time:
                raise BookingError("You cannot authorise booking '%s' as it is in the past." % reservation,
                                   detail = BookingInfo(booking))
            elif booking.start_time <= now_time:
                raise BookingError("""You cannot authorise booking '%s' as it has already started.
                                      Please ask the user to cancel the booking and remake it.""" % reservation)

            booking.status = Booking.confirmed()
            booking.put()

    def getBookings(self, account, acl, start_time=None, end_time=None, status=Booking.confirmed()):
        """Get all future bookings of this piece of equipment"""
        return get_bookings(self, start_time=start_time, end_time=end_time, status=status, sorted=True)

    def getPendingBookings(self, account, acl):
        """Get all future bookings that must be authorised"""
        return get_bookings(self, start_time=get_now_time(), status=Booking.pendingAuthorisation(), sorted=True)

    def getUnresolvedFeedBack(self):
        """Return all of the unresolved feedback about this piece of equipment"""
        return feedback.FeedBackInfo.getUnresolvedFeedBackForEquipment(self)

    def getRequirements(self, create_if_nonexistant=False):
        """Return the requirements that must be supplied by the user when booking
           this equipment. Note that this grabs the requirements from the equipment
           type if none have been specified"""
        if self.requirements:
            return EquipmentReqsInfo(reqs_id=self.requirements, registry=self._registry)
        else:
            reqs = self.getEquipmentType().getRequirements(self._registry)

            if reqs:
                item = self._getFromDB()
                requirements = reqs.duplicateAndStore(self._registry)
                item.requirements = requirements.reqs_id
                item.put()

                self.requirements = requirements.reqs_id

                return requirements

            elif create_if_nonexistant:
                reqs = EquipmentReqs( parent=equipment_key(self._registry),
                                      needs_authorisation=False )
                reqs.put()

                requirements = EquipmentReqsInfo(reqs)

                item = self._getFromDB()
                item.requirements = requirements.reqs_id
                item.put()

                self.requirements = requirements.reqs_id
                return reqs
            else:
                return None

    def getConstraints(self, create_if_nonexistant=False):
        """Return the booking constraints that apply at the time of booking this equipment"""
        if self.constraints:
            return self.constraints
        elif create_if_nonexistant:
            item = self._getFromDB()
            item.constraints = BookingConstraint.createFrom( BookingConstraintInfo() )
            item.put()
            self.constraints = BookingConstraintInfo(item.constraints)
            return self.constraints
        else:
            return None

def get_equipment(idstring, registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Return the piece of equipment matching the IDString 'idstring'"""
    return _db.get_item(Equipment, EquipmentInfo, idstring, registry)

def get_booking(idstring, registry=DEFAULT_BOOKING_REGISTRY):
    """Return the booking matching the IDString 'idstring'"""
    return _db.get_item(Booking, BookingInfo, idstring, registry)

def list_equipment(sorted=True, equipment_registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Return a list of all pieces of equipment"""
    return _db.list_items(Equipment, EquipmentInfo, equipment_registry, sorted)

def get_equipment_dict(equipment_registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Return a dictionary of all equipment indexed by ID"""
    d = {}
    equips = list_equipment(False, equipment_registry)
    for equip in equips:
        d[equip.idstring] = equip
    return d

def list_equipment_by_type(sorted=True, equipment_registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Return a dictionary of all pieces of equipment, keyyed by equipment type"""
    items = list_equipment(sorted, equipment_registry)

    output = {}

    for item in items:
        if not (item.equipment_type in output):
            output[item.equipment_type] = []

        output[item.equipment_type].append(item)

    return output

def list_equipment_by_laboratory(sorted=True, equipment_registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Return a dictionary of all pieces of equipment, keyyed by laboratory"""
    items = list_equipment(sorted, equipment_registry)

    output = {}

    for item in items:
        if not (item.laboratory in output):
            output[item.laboratory] = []

        output[item.laboratory].append(item)

    return output

def list_equipment_in_laboratory(laboratory, sorted=True, registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Return the list of equipment that is held in the passed laboratory"""
    if not laboratory:
        return None

    items = Equipment.getQuery(registry).filter(Equipment.laboratory==laboratory.idstring).fetch()

    if items:
        if sorted:
            sorted_items = {}

            for item in items:
                sorted_items[item.name] = EquipmentInfo(item)

            keys = list(sorted_items.keys())
            keys.sort()

            output = []
            for key in keys:
                output.append(sorted_items[key])

            return output
        else:
            output = []
            for item in items:
                output.append( EquipmentInfo(item) )
            return output
    else:
        return None

def list_equipment_with_type(equip_type, sorted=True, registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Return the list of equipment that is of the specified type"""
    if not equip_type:
        return None

    items = Equipment.getQuery(registry).filter(Equipment.equipment_type==equip_type.idstring).fetch()

    if items:
        if sorted:
            sorted_items = {}

            for item in items:
                sorted_items[item.name] = EquipmentInfo(item)

            keys = list(sorted_items.keys())
            keys.sort()

            output = []
            for key in keys:
                output.append(sorted_items[key])

            return output
        else:
            output = []
            for item in items:
                output.append( EquipmentInfo(item) )
            return output
    else:
        return None

def list_equipment_types(sorted=True, types_registry=DEFAULT_TYPES_REGISTRY):
    """Return a list of all equipment types"""
    return _db.list_items(EquipmentType, EquipmentTypeInfo, types_registry, sorted)

def list_laboratories(sorted=True, labs_registry=DEFAULT_LABS_REGISTRY):
    """Return a list of all laboratory types"""
    return _db.list_items(Laboratory, LaboratoryInfo, labs_registry, sorted)

def get_equipment_mapping(registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Return the dictionary mapping equipment ID strings to equipment names"""
    return _db.get_idstring_to_name_db(Equipment, registry)

def get_laboratory_mapping(registry=DEFAULT_LABS_REGISTRY):
    """Return the dictionary mapping laboratory ID strings to laboratory names"""
    return _db.get_idstring_to_name_db(Laboratory, registry)

def get_equipment_type_mapping(registry=DEFAULT_TYPES_REGISTRY):
    """Return the dictionary mapping equipment type ID strings to equipment type names"""
    return _db.get_idstring_to_name_db(EquipmentType, registry)

def get_sorted_equipment_mapping(registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Return a sorted list of all equipment names, together with their idstrings"""
    return _db.get_sorted_names_to_idstring(Equipment,registry)

def get_sorted_equipment_type_mapping(registry=DEFAULT_TYPES_REGISTRY):
    """Return a sorted list of all equipment type names, together with their idstrings"""
    return _db.get_sorted_names_to_idstring(EquipmentType,registry)

def get_sorted_laboratory_mapping(registry=DEFAULT_LABS_REGISTRY):
    """Return a sorted list of all laboratory names, together with their idstrings"""
    return _db.get_sorted_names_to_idstring(Laboratory,registry)

def changed_laboratory_info(registry=DEFAULT_LABS_REGISTRY):
    """Function called whenever lab info is changed"""
    memcache.set("lab_for_equip_mapping", None)
    memcache.set("equip_fullname_to_idstring", None)
    _db.changed_idstring_to_name_db(Laboratory, registry)

def changed_type_info(registry=DEFAULT_TYPES_REGISTRY):
    """Function called whenever equipment type info is changed"""
    memcache.set("type_for_equip_mapping", None)
    memcache.set("equip_fullname_to_idstring", None)
    _db.changed_idstring_to_name_db(EquipmentType, registry)

def changed_equipment_info(registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Function called whenever equipment info is changed"""
    memcache.set("lab_for_equip_mapping", None)
    memcache.set("type_for_equip_mapping", None)
    memcache.set("equip_fullname_to_idstring", None)
    _db.changed_idstring_to_name_db(Equipment, registry)

def get_equipment_hierarchy(registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Function called to get a list of lists of how equipment is arranged into labs and types"""

    k = "equip_fullname_to_idstring"
    d = memcache.get(k)

    if d:
        return d
    else:
        items = Equipment.getQuery(registry).fetch()    

        labs = {}

        for item in items:
            i = EquipmentInfo(item)
            labname = i.getLaboratoryName()
            typname = i.getEquipmentTypeName()

            if not (labname in labs):
                labs[labname] = {}

            if not (typname in labs[labname]):
                labs[labname][typname] = {}

            labs[labname][typname][i.name] = i.idstring

        labnames = list(labs.keys())
        labnames.sort()

        lab_output = []

        for labname in labnames:
            typnames = list(labs[labname].keys())
            typnames.sort()

            typ_output = []

            for typname in typnames:
                equipnames = list(labs[labname][typname].keys())
                equipnames.sort()

                equip_output = []

                for equipname in equipnames:
                    equip_output.append( (equipname, labs[labname][typname][equipname]) )

                typ_output.append( (typname, equip_output) )

            lab_output.append( (labname, typ_output) )

        memcache.set(key=k, value=lab_output)
        return lab_output

def get_laboratory_for_equipment_mapping(equip_reg=DEFAULT_EQUIPMENT_REGISTRY,labs_reg=DEFAULT_LABS_REGISTRY):
    """Return a dictionary of the laboratories for each piece of equipment, 
       indexed by piece of equipment"""
    k = "lab_for_equip_mapping"
    d = memcache.get(k)

    if d:
        return d
    else:
        d = {}
        items = Equipment.getQuery(equip_reg).fetch()

        labs_mapping = get_laboratory_mapping(labs_reg)

        for item in items:
            d[unicode(item.key.string_id())] = (unicode(item.laboratory), unicode(labs_mapping[item.laboratory]))

        memcache.set(key=k, value=d)

        return d

def get_type_for_equipment_mapping(equip_reg=DEFAULT_EQUIPMENT_REGISTRY,types_reg=DEFAULT_TYPES_REGISTRY):
    """Return a dictionary of the equipment types for each piece of equipment, 
       indexed by piece of equipment"""
    k = "type_for_equip_mapping"
    d = memcache.get(k)

    if d:
        return d
    else:
        d = {}
        items = Equipment.getQuery(equip_reg).fetch()

        types_mapping = get_equipment_type_mapping(types_reg)

        for item in items:
            d[unicode(item.key.string_id())] = (unicode(item.equipment_type), unicode(types_mapping[item.equipment_type]))

        memcache.set(key=k, value=d)

        return d

def get_acl(equipment, email, registry=DEFAULT_ACLS_REGISTRY):
    """Return the ACL for the equipment with idstring 'equipment' for the 
       user with email 'email'"""

    if not equipment or email:
        return None

    acls = EquipmentACL.getQuery(registry)\
                       .filter( EquipmentACL.user == email )\
                       .filter( EquipmentACL.equipment == equipment ).fetch(1)

    if acls:
        return EquipmentACLInfo(acls[0])
    else:
        return None

def get_acls_for_email(email, registry=DEFAULT_ACLS_REGISTRY):
    """Return all of the ACLs that match the email 'email'"""
    if not email:
        return None

    acls = EquipmentACL.getQuery(registry)\
                       .filter( EquipmentACL.user == email ).fetch()

    if acls:
        output = []

        for acl in acls:
            output.append( EquipmentACLInfo(acl) )

        return output
    else:
        return None

def sort_equipment(equipment):
    """Sort the passed list of equipment so that it is listed in order
       of type and then name"""
    return equipment

def get_administered_equipment(account, sorted=True):
    """Return all of the equipment that is administered by this user"""

    if not account or not account.is_approved:
        return None

    # Get a list of all ACLs for this user
    acls = get_acls_for_email(account.email)

    if not acls:
        return None

    output = []

    for acl in acls:
        if acl.isAdmin():
            output.append( get_equipment(acl.equipment) )

    if sorted:
        return sort_equipment(output)
    else:
        return output

def get_authorised_equipment(account, sorted=True):
    """Return all of the equipment that this account is authorised to use"""

    if not account or not account.is_approved:
        return None

    # Get a list of all ACLs for this user
    acls = get_acls_for_email(account.email)

    if not acls:
        return None

    output = []

    for acl in acls:
        if acl.isAuthorised():
            output.append( get_equipment(acl.equipment) )

    if sorted:
        return sort_equipment(output)
    else:
        return output

def get_pending_equipment(account, sorted=True):
    """Return all of the equipment that this account is awaiting access (is pending)"""

    if not account or not account.is_approved:
        return None

    # Get a list of all ACLs for this user
    acls = get_acls_for_email(account.email)

    if not acls:
        return None

    for acl in acls:
        if acl.isPending():
            output.append( get_equipment(acl.equipment) )

    if sorted:
        return sort_equipment(output)
    else:
        return output

def validate_time(time):
    """Validate that the passed object is a date/time and return this
       object converted to a Python datetime object"""
    if time.__class__ is datetime.datetime:
        return time
    else:
        try:
            # get a datetime from the passed isoformat string - assume user strings are in GMT time
            return to_utc(datetime.datetime( *map(time, re.split('[^\d]', dt)[:-1]), tzinfo=GMT_TZ() ))
        except:
            raise BookingError( """Cannot understand the passed time '%s'. Valid times should
                                   either be datetime.datetime objects or iso format strings.""" % time )

def sort_times(start_time, end_time):
    """Ensures that start_time is earlier than end_time"""
    start_time = validate_time(start_time)
    end_time = validate_time(end_time)

    if start_time > end_time:
        return (end_time, start_time)
    else:
        return (start_time, end_time)

def get_bookings_for_user(account, range_start=None, range_end=None, sorted=True,
                          reverse_sort=False, registry=DEFAULT_BOOKING_REGISTRY):
    """Return all bookings for the passed user. If range_start or range_end are specified then these
       limit the ranges to only those bookings that include the passed times"""

    if not account or not account.is_approved:
        return None

    double_range=False

    if range_start and range_end:
        double_range=True

        if range_start > range_end:
            tmp = range_start
            range_start = range_end
            range_end = tmp
        elif range_start == range_end:
            return []

    query = Booking.getQuery(registry).filter(Booking.user==account.email)

    if range_start:
        query = query.filter( Booking.end_time > range_start )
    elif range_end:
        query = query.filter( Booking.end_time <= range_end )

    items = query.fetch()

    bookings = []

    if double_range:
        for item in items:
            if item.end_time <= range_end:
                bookings.append( BookingInfo(item) )
    else:
        for item in items:
            bookings.append( BookingInfo(item) )

    if sorted:
        bookings.sort(key=lambda x: x.start_time, reverse=reverse_sort)

    return bookings

def get_bookings(equipment=None, start_time=None, end_time=None, status=None, 
                 sorted=True, reverse_sort=False, registry=DEFAULT_BOOKING_REGISTRY):
    """Return all bookings for the passed piece of equipment between 'start_time' and "end_time.
       If 'equipment' is None, then this returns the bookings for all equipment. If 'start_time'
       or 'end_time' are None then they default to the beginning or end of time."""

    if equipment:
        try:
            equipment = equipment.idstring
        except:
            pass

        query = Booking.getEquipmentQuery(equipment,registry)
    else:
        query = Booking.getQuery(registry)

    if status:
        query = query.filter( Booking.status == status )

    double_range=False

    if start_time and end_time:
        double_range=True

        if start_time > end_time:
            tmp = start_time
            start_time = end_time
            end_time = tmp
        elif start_time == end_time:
            return []

    if start_time:
        query = query.filter( Booking.end_time > start_time )
    elif end_time:
        query = query.filter( Booking.start_time <= end_time )

    items = query.fetch()

    bookings = []

    if double_range:
        for item in items:
            if item.start_time <= end_time:
                bookings.append( BookingInfo(item) )
    else:
        for item in items:
            bookings.append( BookingInfo(item) )

    if sorted:
        bookings.sort(key=lambda x: x.start_time, reverse=reverse_sort)

    return bookings

def number_of_equipment(equipment_registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Function to return the total number pieces of equipment"""
    return _db.number_of_items(Equipment, equipment_registry)

def number_of_equipment_types(equipment_type_registry=DEFAULT_TYPES_REGISTRY):
    """Function to return the total number types of equipment"""
    return _db.number_of_items(EquipmentType, equipment_type_registry)

def number_of_laboratories(labs_registry=DEFAULT_LABS_REGISTRY):
    """Function to return the total number laboratories"""
    return _db.number_of_items(Laboratory, labs_registry)

def number_of_bookings(bookings_registry=DEFAULT_BOOKING_REGISTRY):
    """Function to return the total number of bookings"""
    return _db.number_of_items(Booking, bookings_registry)

def get_sorted_equipment_for_account(account):
    """Return all of the equipment IDstrings associated with the account 'account', sorted
       into lists in a dictionary for administered, authorised, pending and banned"""

    output = {}

    admin = []
    auth = []
    pend = []
    band = []

    acls = EquipmentACLInfo.getRulesForAccount(account)

    if acls:
        for acl in acls:
            if acl.isAdministrator():
                admin.append(acl.equipment)

            if acl.isAuthorised():
                auth.append(acl.equipment)
            elif acl.isPending():
                pend.append(acl.equipment)
            elif acl.isBanned():
                band.append(acl.equipment)

    if len(admin) > 0:
        admin.sort()
        output["administered"] = admin

    if len(auth) > 0:
        auth.sort()
        output["authorised"] = auth

    if len(pend) > 0:
        pend.sort()
        output["pending"] = pend

    if len(band) > 0:
        band.sort()
        output["banned"] = band

    return output

def add_equipment(account, item_name, item_type, item_lab, registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Function called to add a new piece of equipment called 'item_name', with 
       type and laboratory identified by their passed idstrings. Only admin accounts
       are allowed to add new pieces of equipment."""

    if not item_name or not item_type or not item_lab:
        return None

    item_name = to_string(item_name)
    item_type = to_string(item_type)
    item_lab = to_string(item_lab)

    # create an IDString that amalgamates the name, type and lab
    idstring = name_to_idstring("%s_%s_%s" % (item_name, item_type, item_lab))

    info = {}
    info["idstring"] = idstring
    info["item_name"] = item_name
    info["item_type"] = item_type
    info["item_lab"] = item_lab

    if not idstring:
        raise InputError("You cannot create a new item of equipment without a valid name!", info)

    item = get_equipment(idstring)

    if item:
        info["old item"] = item

        raise InputError("""You cannot add a new item of equipment that has a similar name to an item
                            of equipment that exists already with the same type and in the same laboratory.
                            The name of your new item of equipment '%s' is too similar to the name of an
                            existing item of equipment '%s'.""" % \
                              (item_name, item.name), info)

    # ensure that the laboratory and equipment type are valid
    lab = get_laboratory(item_lab)

    if not lab:
        raise InputError("""Cannot find the laboratory for new equipment item '%s' that matches the 
                            IDString '%s'. Cannot add the piece of equipment.""" % (item_name,item_lab), info)

    type = get_equipment_type(item_type)

    if not type:
        raise InputError("""Cannot find the equipment type for new equipment item '%s' that matches the 
                            IDString '%s'. Cannot add the piece of equipment.""" % (item_type,item_lab), info)

    # everything is ok, add the equipment item
    try:
        item = Equipment( parent = equipment_key(registry),
                          id = idstring,
                          name = item_name,
                          equipment_type = item_type,
                          laboratory = item_lab )                          
        item.put()

        changed_equipment_info(registry)

    except Exception as e:
        raise InputError("""Problem adding a new piece of equipment to the database! Please check the detailed
                            error message.""", detail=info, json=e)

    info = EquipmentInfo(item,registry)

    try:
        info.createCalendar(account)
    except:
        pass

    return info

def delete_equipment(account, idstring, registry=DEFAULT_EQUIPMENT_REGISTRY):
    """Function used to delete an item of equipment from the system"""
    assert_is_admin(account, "Only administrators can delete items of equipment from the system!")

    if not idstring:
        return

    item = _db.get_db(Equipment, idstring, registry)

    if item:

        if item.calendar:
            # we don't need this calendar any more
            calendar.delete_calendar(account, item.calendar)

        item.key.delete()

        changed_equipment_info(registry)


def add_equipment_type(account, type_name, types_registry=DEFAULT_TYPES_REGISTRY):
    """Function called to add a new equipment type with the passed name. Only
       admin accounts are allowed to add new equipment types."""

    if not type_name:
        return None

    type_name = to_string(type_name)
    idstring = name_to_idstring(type_name)

    info = {}
    info["idstring"] = idstring
    info["type_name"] = type_name

    if not idstring:
        raise InputError("You cannot create a new equipment type without a valid name!", info)

    typ = get_equipment_type(idstring)

    if typ:
        raise InputError("""You cannot add a new equipment type that has a similar name to an equipment 
                            type that exists already. The name of your new equipment type '%s' is too similar
                            to the name of an existing equipment type '%s'.""" % (type_name, typ.name), info)

    try:
        typ = EquipmentType( parent = types_key(types_registry),
                             id = idstring,
                             name = type_name )

        typ.put()

        changed_type_info(types_registry)

    except Exception as e:
        raise InputError("""Problem adding an equipment type to the database! Please check the detailed 
                            error message.""", detail=info, json=e)

    return EquipmentTypeInfo(typ,types_registry) 

def delete_equipment_type(account, idstring, registry=DEFAULT_TYPES_REGISTRY):
    """Function used to delete an equipment type from the system"""
    assert_is_admin(account, "Only administrators can delete equipment types from the system!")

    if not idstring:
        return

    item = _db.get_db(EquipmentType, idstring, registry)

    if item:
        item.key.delete()
        changed_type_info(registry)


def add_laboratory(account, lab_name, lab_owners, labs_registry=DEFAULT_LABS_REGISTRY):
    """Function called to add a new laboratory with the passed information. Only admin
       accounts are allowed to add new laboratories."""
    
    if not lab_name:
        return None

    assert_is_admin(account, "You need to be an administrator to be able to add laboratories.")

    lab_name = to_string(lab_name)
    lab_owners = to_list(lab_owners, ",")

    idstring = name_to_idstring(lab_name)

    info = {}
    info["idstring"] = idstring
    info["lab_name"] = lab_name
    info["lab_owners"] = lab_owners

    if not idstring:
        raise InputError("You cannot create a new lab without a valid name!", info)

    lab = get_laboratory(idstring)

    if lab:
        raise InputError("""You cannot add a new laboratory that has a similar name to a laboratory
                            that exists already. The name of your new laboratory '%s' is too similar
                            to the name of an existing laboratory '%s'.""" % (lab_name, lab.name), info)


    try:
        lab = Laboratory( parent = labs_key(labs_registry),
                          id = idstring,
                          name = lab_name,
                          owners = lab_owners )

        lab.put()
        changed_laboratory_info(labs_registry)

    except Exception as e:
        raise InputError("""Problem adding the laboratory to the database! Please check the detailed 
                            error message.""", detail=info, json=e)

    return LaboratoryInfo(lab,labs_registry)

def delete_laboratory(account, idstring, registry=DEFAULT_LABS_REGISTRY):
    """Function used to delete a laboratory from the system"""
    assert_is_admin(account, "Only administrators can delete laboratories from the system!")

    if not idstring:
        return

    item = _db.get_db(Laboratory, idstring, registry)

    if item:
        item.key.delete()
        changed_laboratory_info(registry)
