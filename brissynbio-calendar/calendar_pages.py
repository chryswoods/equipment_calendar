# -*- coding: utf-8 -*-

import webapp2

# base pages
import base_pages

# BSB interface
import bsb

from oauth2client import client

class CalendarOAuth2Page(base_pages.BaseOAuth2Page):
    """Class that handles the oauth2 response for the calendar"""

    def needsAccount(self):
        return True

    def needsAdmin(self):
        return True

    def acceptCode(self, state, code):
        """Function called by the base page to peform the second stage
           of authentication based on the passed one-time code 'code'"""
        bsb.calendar.setCalendarAccount(state.account, code)        


def writeCalendarIsUnavailable(page, state):
    """Function called to write a 'calendar is unavailable message to the screen"""
    state.addError("""Cannot view the calendar pages when the calendar account has
                      not been connected to the website. Please ask an administrator
                      to login and connect the calendar account.""")

    page.write(state, "calendar_unavailable.html", "Calendar is Unavailable")


def writeCalendarTokenExpired(page, state):
    """Function called to write a 'calendar token has expired' message to the screen"""
    state.addError("""Cannot view the calendar pages as the access token has expired.
                      Please ask an administrator to login and refresh the access tokens.""")

    page.write(state, "calendar_unavailable.html", "Calendar is Unavailable")


class DisconnectCalendarPage(base_pages.BaseGetPage):
    """Class the disconnects the calendar account from the website"""

    def needsAdmin(self):
        return True

    def saveReferrer(self):
        return False

    def render_get(self, state):
       self.setReferrer("/admin")

       if bsb.calendar.hasCalendarAccount():
           if self.request.get("really") == "true":
               bsb.calendar.disconnectCalendarAccount(state.account)
               state.setTemplate("header", "The calendar account has been disconnected.")
               state.addMessage("Click here if you want to reconnect the calendar account.")
               session_key = self.createSessionKey()
               state.setTemplate("message_url", bsb.calendar.connectCalendarAccountURL(session_key))
           else:
               state.setTemplate("header", "Do you really want to disconnect the calendar account?")
               state.addMessage("Click here if you are really sure!")
               state.setTemplate("message_url", "%s?really=true" % self.request.uri)
       else:
           state.setTemplate("header", "The calendar account has been disconnected.")
           state.addMessage("Click here if you want to connect the calendar account.")
           session_key = self.createSessionKey()
           state.setTemplate("message_url", bsb.calendar.connectCalendarAccountURL(session_key))

       self.write(state, "message.html", "Do you really want to disconnect?")

class CalendarNotConnectedPage(base_pages.BaseGetPage):
    """Class that prints the message that a calendar is not connected"""

    def render_get(self, state):
        calendar = bsb.calendar.get_calendar( state.account, self.request.get("calendar",None) )

        if calendar:
            state.addMessage("The calendar '%s' is not connected to Google Calendar." % calendar.name)

        self.write(state, "message.html", "Calendar | Not connected")

class CalendarNotVisiblePage(base_pages.BaseGetPage):
    """Class that prints the message that a calendar is not visible to this user"""

    def render_get(self, state):
        calendar = bsb.calendar.get_calendar( state.account, self.request.get("calendar",None) )

        if calendar:
            state.addMessage("The calendar '%s' is not visible to your account '%s'." \
                               % (calendar.name, state.account.email) )

        self.write(state, "message.html", "Calendar | Not visible")
