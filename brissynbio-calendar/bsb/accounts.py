# -*- coding: utf-8 -*-

"""Module containing all classes needed to describe and manage the 
   user accounts used by the BrisSynBio equipment scheduler"""

from google.appengine.ext import ndb

# copy module
import copy

# cgi module
import cgi

# random module
import random

# regular expression module used to validate user account details
import re

# import the project stuff
import projects

from bsb import *

# uses the db module, which should be kept private
import bsb._db as _db

class AccountError(SchedulerError):
    pass

class MissingAccountError(AccountError):
    pass

# The default registry of user accounts
DEFAULT_USERACCOUNT_REGISTRY = "bsb.equipment.users"

def user_account_key(useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Constructs a Datastore key for a user account entry.
       We use the account name as the key"""
    return ndb.Key('Accounts', useraccount_registry)

class Account(ndb.Model):
    """The main model for representing an individual user account."""

    # Nickname - used when writing nice text to the user
    name = ndb.StringProperty(indexed=False)
    # 3-letter initials that can be used for quick authentication
    # and identification (e.g. writing them on flasks)
    initials = ndb.StringProperty(indexed=True)
    # pin number used to add bookings when using a shared terminal
    # (lower security, but only available in labs)
    pin_number = ndb.StringProperty(indexed=False)
    # the text submitted by the user to say who they are when requesting
    # an account
    intro_text = ndb.StringProperty(indexed=False)
    # the default project that should be used when booking time
    default_project = ndb.StringProperty(indexed=False)
    # Whether or not this user has been approved as a bona-fide 
    # person who has access to the equipment
    is_approved = ndb.BooleanProperty(indexed=False)
    # Whether or not this user has administration rights on 
    # the equipment booking system
    is_admin = ndb.BooleanProperty(indexed=False)
    # Human readable information about the user
    information = ndb.JsonProperty(indexed=False)

    def setFromInfo(self, info):
        _db.setFromInfo(self, info)
        self.initials = info.initials
        self.intro_text = info.intro_text
        self.pin_number = info.pin_number
        self.default_project = info.default_project
        self.is_approved = info.is_approved
        self.is_admin = info.is_admin

    @classmethod
    def getQuery(cls, registry=DEFAULT_USERACCOUNT_REGISTRY):
        return cls.query(ancestor=user_account_key(registry))

    @classmethod
    def ancestor(cls, registry=DEFAULT_USERACCOUNT_REGISTRY):
        return user_account_key(registry)

class AccountInfo(_db.StandardInfo):
    """Simple class that holds the non-sensitive information about an account"""
    def __init__(self, account=None, registry=DEFAULT_USERACCOUNT_REGISTRY):
        _db.StandardInfo.__init__(self, account, registry)

        self.initials = None
        self.intro_text = None
        self.default_project = None
        self.is_approved = False
        self.is_admin = False

        if account:
            if account.initials:
                self.initials = unicode(account.initials)
            if account.intro_text:
                self.intro_text = unicode(account.intro_text)
            if account.default_project:
                self.default_project = unicode(account.default_project)
            if account.pin_number:
                self.pin_number = unicode(account.pin_number)

            self.email = self.idstring
            self.is_approved = account.is_approved
            self.is_admin = account.is_admin

    def __str__(self):
        return "%s (%s - %s)" % (self.name, self.email, self.initials)

    def publicData(self):
        """Return a copy of this account with only public data visible"""
        val = copy.copy(self)
        val.pin_number = None
        return val

    @classmethod
    def getAll(cls, account, registry=None):
        """Return all of the items in the database"""
        return _db.getAllFromDB(account, Account, registry)

    @classmethod
    def backup(cls, account, registry=None):
        """Return a string containing the entire database in pickled form"""
        return _db.backup(account, cls, Account, registry)

    @classmethod
    def restore(cls, account, data, registry=None):
        """Restore the database from the passed 'data' string containing a pickle of all of the objects"""
        _db.restore(account, cls, Account, data, registry, delete_existing=False)

    @classmethod
    def deleteDB(cls, account, registry=None):
        """Delete the entire database"""
        _db.deleteDB(account, cls, Account, registry)

def list_accounts(sorted=True, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function to return a string containing a list of all user accounts"""
    return _db.list_items(Account, AccountInfo, useraccount_registry, sorted)

def number_of_accounts(useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function to return the total number of user accounts"""
    return _db.number_of_items(Account, useraccount_registry)

def number_of_admin_accounts(useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function to return the total number of admin accounts"""

    accounts = list_accounts(False, useraccount_registry)

    nadmin = 0

    for account in accounts:
        if account.is_admin and account.is_approved:
            nadmin += 1

    return nadmin

def number_of_account_to_approve(useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function to return the total number of accounts that need to be approved"""

    accounts = list_accounts(False, useraccount_registry)

    napprove = 0

    for account in accounts:
        if not account.is_approved:
            napprove += 1

    return napprove

def get_account_by_email_unchecked(email, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    email = to_email(email)

    if email is None:
        return None

    account = _db.get_item(Account, AccountInfo, email, useraccount_registry)
    return account.publicData()

def get_account_by_email(admin_account, email, 
                         useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Funcion to return the account model associated with the
       passed email. Note that you have to pass your account to 
       ensure that you have admin access to this data. Note that this
       returns an AccountInfo object, rather than an Account object"""

    email = to_email(email)

    if email is None:
        return None

    if not admin_account.is_admin:
       return None

    return _db.get_item(Account, AccountInfo, email, useraccount_registry)

def has_account_by_email(email, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Return whether or not there is an account with email 'email'."""

    email = to_email(email)

    account = _db.get_item(Account, AccountInfo, email, useraccount_registry)

    if account:
        return True
    else:
        return False

def get_account_by_initials(admin_account, initials, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function to return the account model associated with the
       passed initials. This returns None if there is not account
       registered with these initials"""

    initials = to_string(initials)

    if initials is None:
        return None

    if not admin_account.is_admin:
       return None

    accounts = Account.getQuery(useraccount_registry)\
                      .filter( Account.initials == initials ).fetch(1)

    if accounts:
        return AccountInfo(accounts[0])
    else:
        return None

def get_account_mapping(registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Return the dictionary mapping account emails to account names"""
    return _db.get_idstring_to_name_db(Account, registry)

def get_sorted_account_mapping(registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Return a sorted list of all account names, together with their emails"""
    return _db.get_sorted_names_to_idstring(Account,registry)

def has_account_by_initials(initials, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Return whether or not there is an account with initials 'initials'."""

    initials = to_string(initials)

    if initials is None:
        return False

    accounts = Account.getQuery(useraccount_registry)\
                      .filter( Account.initials == initials ).fetch(1)

    if accounts:
        return True
    else:
        return False
    

def get_account(user, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function to return the account associated with the 
       passed credentials. This returns None if the user is not 
       registered with this system"""

    if user is None:
        return None

    email = to_email(user.email())

    return _db.get_item(Account, AccountInfo, email, useraccount_registry)    

def get_view_account(account, email, registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function to return a view of the account associated with the passed email address.
       This returns only non-private information"""
    if not account.is_approved:
        return None

    email = to_email(email)

    if not email:
        return None

    a = _db.get_item(Account, AccountInfo, email, registry)

    if not a:
        raise MissingAccountError("No account registered with email address '%s'" % email)

    if account.email == email:
        return a
    else:
        return a.publicData()

def _get_account_db(user, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function to return the account associated with the 
       passed credentials. This returns None if the user is not 
       registered with this system"""

    if user is None:
        return None

    email = to_email(user.email())

    return _db.get_db(Account, email, useraccount_registry)    


class AddAccountError:
    def __init__(self, errors):
        self._errors = errors

    def __str__(self):
        return "AddAccountError(%s)" % repr(self._errors)

    def errors(self):
        return self._errors

def validate_pin_number(pin_number):
    """Validates the passed pin number. This returns a list of errors if there is anything wrong"""

    errors = []

    pin_number = to_string(pin_number)

    if not pin_number:
        errors.append( "Please enter a PIN number. This should be four digits.")
        return errors

    # validate that the pin number is 4 number digits
    if len(pin_number) < 4:
        errors.append( "You cannot use \"%s\" as a pin number as it contains less than 4 digits" % pin_number )
    elif len(pin_number) > 4:
        errors.append( "You cannot use \"%s\" as a pin number as it contains more than 4 digits" % pin_number )

    if len(pin_number) < 5:
        is_numeric = True

        for number in pin_number:
            if not re.match(r"[0-9]", number):
                is_numeric = False

        if not is_numeric:
            errors.append( "You cannot use \"%s\" as a pin number as it must only contain numbers (0-9)" % pin_number )


    # now check that the pin number is not too simple
    first_num = int(pin_number[0])
    last_num = first_num

    too_simple = True

    seen = {}
    seen[first_num] = 1

    for number in pin_number[1:]:
        n = int(number)
        seen[n] = 1

        if n != first_num and n != last_num + 1 and n != last_num - 1:
            too_simple = False

        last_num = n

    if too_simple or len(seen.keys()) < 3:
        errors.append( "Your chosen pin number \"%s\" is too simple and easily guessed. You cannot use lots of repeated numbers (e.g. 1111, 1112, 8887), nor simple sequences of numbers (e.g. 1234, 9876), and your number must contain at least three different digits (e.g. 1133 is too simple)." % pin_number )
    
    return errors
        

def add_account(user, name, initials, intro_text, 
                chosen_project, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function used to register the passed user with the system"""

    # first, see if the account has already been registered
    account = get_account(user, useraccount_registry)

    if account:
        # it has, there is thus nothing to do
        return

    # generate a random 4-digit PIN number
    while True:
        pin_number = "%d%d%d%d" % (random.randint(1,9),random.randint(1,9),random.randint(1,9),random.randint(1,9))
        errors = validate_pin_number(pin_number)
        if len(errors) == 0:
            break

    if name is None:
        errors.append( "Please supply your full name.")
        name = ""

    elif len(name) < 3 or len(name) > 100:
        errors.append( "You cannot use \"%s\" as your name, as we can only store names that are more than two characters and less than 100 characters." % \
                        name )

    if initials is None:
        errors.append( "Please supply your initials." )
        initials = ""

    elif len(initials) < 2 or len(initials) > 3:
        errors.append( "You cannot use \"%s\" as your initials as it must contain only 2 or 3 characters." % initials )
        initials = ""

    initials = initials.upper()

    if len(initials) < 5:
        is_alphabetic = True

        for letter in initials:
            if not re.match(r"[A-Z]", letter):
                is_alphabetic = False

        if not is_alphabetic:
            errors.append( "You cannot use \"%s\" as your initials as it contains more than just the letters A to Z." % initials )

    # now escape and trim the intro text
    if intro_text:
        intro_text = cgi.escape(intro_text)

        if len(intro_text) > 300:
            intro_text = intro_text[0:300]
    else:
        errors.append("You cannot request an account without first telling us something about who you are.")

    # now see if we can find the requested default project
    if chosen_project:
        project = projects.get_project_by_id(chosen_project)

        if not project:
            errors.append("Cannot find the requested default project '%s'" % cgi.escape(chosen_project))
            chosen_project = None
        else:
            chosen_project = project.id
    else:
        errors.append("""You must choose a project to which you will primarily belong. If you belong to
                         more than one project, then choose the project for which you will be using
                         BrisSynBio equipment the most. Do not worry about your choice as you are free
                         to change projects when you book equipment, and you are also able to edit this choice at any time.
                         If you do not know which project to choose, then select "Other...".""")

    email = to_email(user.email())

    if not email:
        errors.append( "Could not get a valid email address from your login? '%s'" % user.email() )

    if len(errors) > 0:
        raise AddAccountError(errors)

    # now see if anyone has used these initials before...
    has_initials = has_account_by_initials(initials, useraccount_registry)

    if has_initials:
        errors.append( "You cannot use \"%s\" as your initials as they are already in use by someone else." % \
                          (initials) )
        raise AddAccountError(errors)
        

    # if there are no existing accounts, then the first account is both approved and is an admin
    is_first_account = (number_of_accounts(useraccount_registry) == 0)

    # ok, we have validated the input. Now let's try to create the account
    account = Account( parent = user_account_key(useraccount_registry),
                       id = email,
                       name = name,
                       initials = initials,
                       intro_text = intro_text,
                       default_project = chosen_project,
                       pin_number = pin_number,
                       is_approved = is_first_account,
                       is_admin = is_first_account )

    account.put()
    _db.changed_idstring_to_name_db(Account,useraccount_registry)

    return


class DeleteAccountError:
    def __init__(self, message):
        self._message = message

    def __str__(self):
        return "DeleteAccountError(%s)" % repr(self._message)

    def message(self):
        return self._message


def delete_account(user, pin_number, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function that is used to delete a user's account. Use with caution!"""

    # validate that the pin number is 4 number digits
    if len(pin_number) != 4:
        raise DeleteAccountError( "Cannot delete account \"%s\" as the pin number \"%s\" does not contain 4 digits" % \
                                    (user.email(), pin_number ) )

    if not re.match(r"\d\d\d\d", pin_number):
        raise DeleteAccountError( "Cannot delete account \"%s\" as the pin number \"%s\" does not contain four digits (numbers only!)" % \
                                    (user.email(), pin_number ) )

    account = get_account(user, useraccount_registry)

    if not account:
        raise DeleteAccountError( "Cannot delete account \"%s\" because it does not exist." % user.email() )

    if account.pin_number != pin_number:
        raise DeleteAccountError(\
          "Cannot delete account \"%s\" because the supplied PIN number \"%s\" does not match that held on record." \
              % (user.email(), pin_number))

    if account.is_admin:
        # count the number of admin accounts - we cannot go below 1 admin account
        nadmin = number_of_admin_accounts(useraccount_registry)

        if nadmin < 2:
            raise DeleteAccountError( """You cannot delete this account as this will not leave any other admin accounts left to administer the system!""" )

    account.key.delete()
    _db.changed_idstring_to_name_db(Account,useraccount_registry)

class AccountPermissionError:
    def __init__(self, errors):
        self._errors = errors

    def __str__(self):
        return "AccountPermissionError(%s)" % repr(self._errors)

    def errors(self):
        return self._errors


def _get_account(account, email, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):

    email = to_email(email)

    if not account.is_admin:
        raise AccountPermissionError( ["You don't have permission to approve accounts!"] )

    account = _db.get_db(Account, email, useraccount_registry)

    if account:
        return account
    else:
        raise AccountPermissionError( ["There is no account matched with email '%s'" % email] )

def approve_account(account, email, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function that approves the account connected to the passed email. Note
       that you have to pass an admin account so that you have permission to
       call this function"""

    account = _get_account(account, email, useraccount_registry)

    if not account.is_approved:
        account.is_approved = True
        account.put()

def make_admin_account(account, email, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function that makes the account connected to the passed email an admin account. Note
       that you have to pass an admin account so that you have permission to
       call this function"""

    account = _get_account(account, email, useraccount_registry)

    if not account.is_approved:
        raise AccountPermissionError( ["You cannot make the account '%s' an admin as it has not yet been approved." % email] )

    if not account.is_admin:
        account.is_admin = True
        account.put()

def revoke_admin_access(account, email, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function that makes the account connected to the passed email not an admin account. Note
       that you have to pass an admin account so that you have permission to
       call this function"""

    account = _get_account(account, email, useraccount_registry)

    # count the number of admin accounts - we cannot go below 1 admin account
    nadmin = number_of_admin_accounts(useraccount_registry)

    if nadmin < 2:
        raise AccountPermissionError( ["""You cannot revoke admin access to this account as this will not leave anyone 
                                          else left who has admin access!"""] )

    if account.is_admin:
        account.is_admin = False
        account.put()

def revoke_access(account, email, useraccount_registry=DEFAULT_USERACCOUNT_REGISTRY):
    """Function that makes the account connected to the passed email not an approved account. Note
       that you have to pass an admin account so that you have permission to
       call this function"""

    account = _get_account(account, email, useraccount_registry)

    if account.is_approved:
        if account.is_admin:
            # count the number of admin accounts - we cannot go below 1 admin account
            nadmin = number_of_admin_accounts(useraccount_registry)

            if nadmin < 2:
                raise AccountPermissionError( ["""You cannot revoke access to this account as this will not leave anyone 
                                                  else left who has admin access!"""] )

            account.is_admin = False
        
        account.is_approved = False
        account.put()

class AccountEditError:
    def __init__(self, errors):
        self._errors = errors

    def __str__(self):
        return "AccountEditError(%s)" % repr(self._errors)

    def errors(self):
        return self._errors

def set_default_project(user, project_id):
    """Function to set the default project for the user 'user' to the project that matches 'project_id'"""
    account = _get_account_db(user)

    if account.default_project == project_id:
        # nothing to do
        return

    # ensure that this project exists
    project = projects.get_project_by_id(project_id)

    if not project:
        raise AccountEditError( ["Cannot change the project as the supplied project '%1' does not appear to exist!" % project_id] )

    account.default_project = project.id
    account.put()

def set_username(user, new_name):
    """Function to change the username/nickname of an account to 'new_username'"""
    account = _get_account_db(user)

    if account.name == new_name:
        # nothing to do
        return

    # validate that the new username is ok
    errors = []

    new_name = to_string(new_name)

    if new_name is None:
        return

    if len(new_name) <= 1:
        errors.append( "Your new username must contain more than one non-space character!" )

    if len(new_name) > 50:
        errors.append( "Your new username should be less than or equal to 50 characters!" )

    if len(errors) > 0:
        raise AccountEditError(errors)

    account.name = new_name
    account.put()
    _db.changed_idstring_to_name_db(Account,DEFAULT_USERACCOUNT_REGISTRY)


def set_pin_number(user, pin_number):
    """Function called to change the pin number of an account"""
    account = _get_account_db(user)

    if account.pin_number == pin_number:
        # nothing to do
        return

    # validate that the new pin number is ok
    errors = validate_pin_number(pin_number)

    if len(errors) > 0:
        raise AccountEditError(errors)

    account.pin_number = pin_number
    account.put()
