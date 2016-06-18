# -*- coding: utf-8 -*-
"""All of the pages used by the application to manage user accounts"""

# needed to handle errors when the deadline for rendering the page has been exceeded
from google.appengine.runtime import DeadlineExceededError

# needed to get information about the user
from google.appengine.api import users

# web application framework
import webapp2
from webapp2_extras import sessions

# to get a traceback from an exception
import traceback

# jinja templateing engine
import jinja2

# standard os library
import os

# standard string and random library to generate the session key
import random
import string
import datetime

# cgi interface
import cgi

import sys

# BSB interface
import bsb

# Set up the jinja environment
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=False)

JINJA_ENVIRONMENT.globals['localise_time'] = bsb.localise_time

admin_email = "brissynbio.equipment@gmail.com"

class MenuItem:
    def __init__(self, text, link=None, submenus=[], is_active=False):
        self.text = text
        self.link = link
        self.submenu_links = submenus
        self.is_active = is_active

    def hasSubmenus(self):
        return len(self.submenu_links) > 0

    def checkActive(self, state):
        submenus = []

        is_active = False

        for submenu in self.submenu_links:
            submenu = submenu.checkActive(state)
            if submenu.is_active:
                is_active = True

            submenus.append(submenu)

        if is_active:
            return MenuItem(self.text, self.link, submenus, True)
        elif self.link == state.current_path:
            return MenuItem(self.text, self.link, submenus, True)
        else:
            for path in state.parent_paths:
                if self.link == path:
                    return MenuItem(self.text, self.link, submenus, True)

            return self

left_menu_items = [ MenuItem("home", "/equipment/summary"),
                    MenuItem("bookings", "/equipment/bookings"),
                    MenuItem("equipment", submenus=[
                                      MenuItem("by laboratory", "/equipment/labs"),
                                      MenuItem("by type", "/equipment/types"),
                                       ]),
                    MenuItem("reports", "/report"),
                    MenuItem("forum", "/forum") ]

admin_menu_item = MenuItem("admin", "/admin")

class DateTimePicker:
    def __init__(self, id_name, has_date=True, has_time=True, mirror_name=None, start_now=False,
                 disabled_days=[]):
        self.id_name = id_name
        self.has_date = has_date
        self.has_time = has_time
        self.mirror_name = mirror_name
        self.start_now = start_now
        self.disabled_days = disabled_days

    def javaScript(self, now_time=None):
        lines = []

        lines.append("$(\".%s\").datetimepicker({ startView: 2" % self.id_name)

        if self.has_date and self.has_time:
            lines.append("format: 'dd MM yyyy, H:ii p'")

            if self.mirror_name:
                lines.append("linkField: '%s'" % self.mirror_name)
                lines.append("linkFormat: 'dd-mm-yyyy hh:ii'")

        elif self.has_date:
            lines.append("format: 'dd MM yyyy'")

            if self.mirror_name:
                lines.append("linkField: '%s'" % self.mirror_name)
                lines.append("linkFormat: 'dd-mm-yyyy'")
                lines.append("minView: 2")

        elif self.has_time:
            lines.append("format: 'H:ii p'")

            if self.mirror_name:
                lines.append("linkField: '%s'" % self.mirror_name)
                lines.append("linkFormat: 'hh:ii'")

        if self.start_now:
            if now_time:
                now_time_string = now_time.strftime("%Y-%m-%d %H:%M")
            else:
                now_time_string = bsb.get_local_now_time().strftime("%Y-%m-%d %H:%M")

            lines.append("startDate: \"%s\"" % now_time_string)
            lines.append("initialDate: \"%s\"" % now_time_string)

        if self.disabled_days and len(self.disabled_days) > 0:
            lines.append("daysOfWeekDisabled: \"[%s]\"" % ",".join(self.disabled_days))

        lines.append("weekStart: 1, autoclose: true, todayHighlight: true")
        lines.append("todayBtn: true, showMeridian: true });")

        return ",\n".join(lines)

class DateTimePickers:
    def __init__(self):
        self.pickers = {}

    def addDatePicker(self, id_name, mirror_name=None, start_now=False, disabled_days=[]):
        self.pickers[id_name] = DateTimePicker(id_name, has_date=True, has_time=False, 
                                               mirror_name=mirror_name, start_now=start_now,
                                               disabled_days=disabled_days)
        return ""

    def addDateTimePicker(self, id_name, mirror_name=None, start_now=False, disabled_days=[]):
        self.pickers[id_name] = DateTimePicker(id_name, has_date=True, has_time=True, 
                                               mirror_name=mirror_name, start_now=start_now,
                                               disabled_days=disabled_days)
        return ""

    def addTimePicker(self, id_name, mirror_name=None, start_now=False):
        self.pickers[id_name] = DateTimePicker(id_name, has_date=False, has_time=True, 
                                               mirror_name=mirror_name, start_now=start_now)
        return ""

    def javaScript(self, now_time=None):
        if len(self.pickers) > 0:
            if not now_time:
                now_time = bsb.get_local_now_time()

            lines = []

            for picker in self.pickers:
                lines.append( self.pickers[picker].javaScript(now_time) )

            return "\n".join(lines)
        else:
            return ""

class PageState:
    def reloadAccountDetails(self):
        """Function used to load all of the account details into the state"""
        self.user = users.get_current_user()

        if self.user:
            self.user_id = self.user.user_id()
        else:
            self.user_id = None

        self.account = bsb.accounts.get_account(self.user)

        if self.account:
            self.template_values["account"] = self.account
            self.template_values["logged_in"] = True
            self.template_values["logout_url"] = users.create_logout_url("/")
            self.template_values["switch_url"] = "/switch_account"
            self.template_values["current_url"] = self.current_path
            now_time = bsb.get_now_time()
            self.template_values["now_time"] = now_time
            self.template_values["email"] = self.account.email
            self.template_values["user"] = self.account.name
            self.template_values["is_admin"] = self.account.is_admin
            self.template_values["is_approved"] = self.account.is_approved
            self.template_values["datetime_pickers"] = DateTimePickers()

        elif self.user:
            self.template_values["email"] = self.user.email()
        else:
            self.template_values["logged_in"] = False
            self.template_values["login_url"] = users.create_login_url("/")


    """Class that is used to hold state during the rendering of a page"""
    def __init__(self, page, args):
        self.template_values = { "admin_email" : admin_email }
        self.current_path = page.request.path
        self.parent_paths = []

        self.reloadAccountDetails()

        if args:
            self.extra_paths = []
            for arg in args:
                self.extra_paths.append( cgi.escape(arg) )
        else:
            self.extra_paths = None

        args = page.request.arguments()

        if len(args) > 0:
            vals = []

            for arg in args:
                vals.append("%s=%s" % (arg, page.request.get(arg)))

            self.template_values["request_arguments"] = "&".join(vals)
            vals = None

        args = None

    def addError(self, error):
        """Add the passed errors to the list of errors for this page"""
        if not error:
            return

        if not "errors" in self.template_values:
            self.template_values["errors"] = []
            self.template_values["has_error"] = True

        message = None

        try:
            message = error.message.lstrip().rstrip()
            if len(message) == 0:
                message = str(error)
        except:
            message = str(error)

        self.template_values["errors"].append(message)

    def addErrors(self, errors):
        """Add the passed errors to the list of errors for this page"""
        for error in errors:
            self.addError(error)

    def addMessage(self, message):
        """Add a message that will be displayed in the message page"""
        if not "messages" in self.template_values:
            self.template_values["messages"] = []

        self.template_values["messages"].append(message)

    def addMessages(self, messages):
        """Add some messages that will be displayed in the message page"""
        for message in messages:
            self.addMessage(message)

    def addParentPage(self, page):
        """Add the passed URL to the list of page parent URLs"""
        self.parent_paths.append(page)

    def setTemplate(self, key, value):
        """Sets the value of 'key' in the template to 'value'"""
        self.template_values[key] = value


class BasePage(webapp2.RequestHandler):
    """Base class of all pages so that we can have a consistent look and feel"""

    def safeInMaintenanceMode(self):
        """Return whether or not this page should be viewable even
           if maintenance mode is switched on"""
        return False

    def needsAuthentication(self):
        """Return whether or not this page should only be viewable by 
           authenticated users"""
        return True

    def needsAccount(self):
        """Return whether or not this page should only be viewable by 
           people with authenticated, authorised accounts"""
        return True

    def needsAdmin(self):
        """Return whether or not this page should only be viewable by
           administrators"""
        return False

    def saveReferrer(self):
        """Return whether or not this page should save its URI as a 
           referrer"""
        return True

    def buildSubMenu(self, state, menu_items):
        """Function to build the submenu into the list of template values"""
        menu = []

        for item in menu_items:
            menu.append( item.checkActive(state) )

        state.template_values["second_menu_links"] = menu

        return state

    def buildMenu(self, state):
        """Function to build the menu into the list of template values"""

        menu = []

        for item in left_menu_items:
            menu.append( item.checkActive(state) )

        if state.account:
            if state.account.is_admin:
                menu.append( admin_menu_item.checkActive(state) )

        state.template_values["left_menu_links"] = menu

        return state

    def setReferrer(self, page):
        """Override the saved referring page to equal 'page'"""
        self.session["referring_page"] = str(page)

    def createSessionKey(self):
        """Create a random session key and store this in the session.
           Returns the created key"""
        session_key = ''.join(random.choice(string.ascii_uppercase + string.digits)
                         for x in xrange(32))
        self.session["session_key"] = session_key
        return session_key

    def sessionKey(self):
        """Return the session key, if one has been set by createSessionKey. Otherwise
           returns None"""
        return self.session.get("session_key", None)

    def validate(self, args):
        # create the page state - this collects the current user id
        state = PageState(self, args)

        if self.needsAuthentication() and (not state.user):
            state.template_values = { 'login_url' : users.create_login_url("/") }
            self.write(state, "login.html", "Login")
            return None

        if self.saveReferrer():
            # save the path to this page. This is useful if we ever redirect away and need
            # to know where we came from
            self.session["referring_page"] = str(self.request.uri)

        if self.needsAccount():
            if not state.account:
                self.redirect("/create_account")
                return None
            elif not state.account.is_approved:
                self.write(state, "unapproved.html", "Unapproved Account")
                return None

        if self.needsAdmin():
            if not state.account.is_admin:
                self.write(state, "notadmin.html", "Permission Denied")
                return None

        if bsb.admin.under_maintenance():
            state.setTemplate("under_maintenance", True)

            if not self.safeInMaintenanceMode():
                self.write(state, "under_maintenance.html", "Under Maintenance")
                return None

        return state

    def write(self, state, template_file, title):
        """Render the page using the passed template file and template values"""
        template = JINJA_ENVIRONMENT.get_template("/templates/%s" % template_file)
        state = self.buildMenu(state)
        state.template_values["title"] = "BSB Equip | %s" % title
        self.response.write(template.render(state.template_values))

    def dispatch(self):
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)

        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()
  

class BaseGetPage(BasePage):
    """Base class of all pages that can only 'get'"""

    def get(self, *args):
        state = self.validate(args)

        try:
            if state:
                self.render_get(state)

        except DeadlineExceededError:
            # if we have run out of time then print an error message to the user
            self.response.clear()
            self.response.set_status(500)
            self.response.out.write("This operation could not be completed in time... The server is too slow.")

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            backtrace = "\n".join(traceback.format_exception(exc_type, exc_value, exc_traceback, limit=20))
            state.setTemplate("exception", e)
            state.setTemplate("backtrace", backtrace)
            bug = bsb.feedback.BugInfo.createFromError(state.account, e, backtrace)

            if bug:
                state.setTemplate("bug_id", bug.bug_id)

            self.write(state, "unhandled_exception.html", "An error occurred!")  

class BasePostPage(BaseGetPage):
    """Base class of all pages that can 'get' and 'post'"""

    def post(self, *args):
        state = self.validate(args)

        try:
            if state:
                 self.render_post(state)

        except DeadlineExceededError:
            # if we have run out of time then print an error message to the user
            self.response.clear()
            self.response.set_status(500)
            self.response.out.write("This operation could not be completed in time... The server is too slow.")

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            backtrace = "\n".join(traceback.format_exception(exc_type, exc_value, exc_traceback, limit=20))
            state.setTemplate("exception", e)
            state.setTemplate("backtrace", backtrace)
            bug = bsb.feedback.BugInfo.createFromError(state.account, e, backtrace)

            if bug:
                state.setTemplate("bug_id", bug.bug_id)

            self.write(state, "unhandled_exception.html", "An error occurred!")  


class SwitchAccountPage(BaseGetPage):
    """Main page used to login to accounts, logout from accounts or switch accounts"""

    def needsAccount(self):
        return False

    def safeInMaintenanceMode(self):
        """Return whether or not this page should be viewable even
           if maintenance mode is switched on"""
        return True

    def saveReferrer(self):
        return False

    def render_get(self, state):
        referring_page = self.session.get("referring_page")

        if not referring_page:
            referring_page = "/"

        login_url = users.create_login_url("/")
        return self.redirect(login_url)


class BaseOAuth2Page(BaseGetPage):
    """Base class of pages that handle the second stage of OAuth2 authentication"""

    def saveReferrer(self):
        return False

    def acceptCode(self, state, code):
        """Overload this function to accept the one-time code
           used to continue with the second stage of authentication"""
        pass

    def render_get(self, state):
        referring_page = str(self.session.get("referring_page"))

        if not referring_page:
            referring_page = "/"

        errors = []

        error = self.request.get("error")

        if error:
            errors.append(error)

        code = self.request.get("code")

        if not code:
            errors.append( "Could not get the authentication code! Could not log in!" )

        session_key = self.sessionKey()
        passed_session_key = self.request.get("state")

        if session_key != passed_session_key:
            errors.append("""The anti-forgery session key test has failed. This may mean
                             that someone is trying to forge one of the login pages so that
                             they can steal your account details. Your account details are safe,
                             but to prevent their loss, you are not able to log in.""")
            errors.append("The session key is: %s" % session_key)
            errors.append("The supplied key is: %s" % passed_session_key)

        if len(errors) > 0:
            state.addErrors(errors)
            state.setTemplate("referring_page", referring_page)
            self.write(state, "oauth2_error.html", "OAuth2 Error")
            return

        # ok - now do something with the authentication code
        try:
            self.acceptCode(state, code)

            # now redirect back to the referring page
            #state.setTemplate("referring_page", referring_page)
            #state.addError("No problem - everything is ok")
            #self.write(state, "oauth2_error.html", "OAuth2 Success")
            self.redirect(referring_page)

        except Exception as e:
            try:
                state.addError(e.error())
            except:
                state.addError(str(e))

            state.setTemplate("referring_page", referring_page)
            self.write(state, "oauth2_error.html", "OAuth2 Error")
