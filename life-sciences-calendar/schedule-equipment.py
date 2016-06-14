# -*- coding: utf-8 -*-
"""Main page of the website and also configure the routes"""

# base pages
import base_pages

# web application framework
import webapp2

#This is needed to configure the session secret key
#Runs first in the whole application
session_config = {}
session_config['webapp2_extras.sessions'] = {
    'secret_key': 'lifesciences-equipment-key-fejwkj2lsllv',
}

class MainPage(base_pages.BaseGetPage):
    """Class that handles the rendering of the main page of the website"""
    def render_get(self, state):
        self.write(state, "index.html", "Home")

# Construct the layout of the website. This is used to associate the classes
# above with different pages of the website
application = webapp2.WSGIApplication([
    ('/', "equipment_pages.EquipmentPage"),
    ('/switch_account', "base_pages.SwitchAccountPage"),
    ('/create_account', "account_pages.CreateAccountPage"),
    ('/delete_account', "account_pages.DeleteAccountPage"),
    ('/equipment', "equipment_pages.EquipmentPage"),
    ('/equipment/([\w_]+)', "equipment_pages.EquipmentPage"),
    ('/equipment/([\w_]+)/([\w_\d@\.]+)', "equipment_pages.EquipmentPage"),
    ('/equipment/([\w_]+)/([\w_\d@\.]+)/([\w_]+)', "equipment_pages.EquipmentPage"),
    ('/equipment/([\w_]+)/([\w_\d@\.]+)/([\w_]+)/([\w_]+)', "equipment_pages.EquipmentPage"),
    ('/account', "account_pages.AccountDetailsPage"),
    ('/account/edit/([\w]+)', "account_pages.AccountDetailsPage"),
    ('/account/view/([\w_\d@\.]+)', "account_pages.AccountViewPage"),
    ('/reports', "report_pages.ReportPage"),
    ('/admin', "admin_pages.AdminPage"),
    ('/admin/summary', "admin_pages.AdminPage"),
    ('/admin/backup', "admin_pages.BackupPage"),
    ('/admin/backup/([\w_\d@\.]+)', "admin_pages.BackupPage"),
    ('/admin/backup/([\w_\d@\.]+)/([\w\d_]+)', "admin_pages.BackupPage"),
    ('/admin/backup/([\w_\d@\.]+)/([\w\d_]+)/([\w\d_]+)', "admin_pages.BackupPage"),
    ('/admin/users', "admin_pages.AdminUsersPage"),
    ('/admin/users/([\w_]+)/([\w_\d@\.]+)', "admin_pages.AdminUsersPage"),
    ('/admin/projects', "admin_pages.AdminProjectsPage"),
    ('/admin/projects/([\w_]+)/([\w_\d@\.]+)', "admin_pages.AdminProjectsPage"),
    ('/admin/projects/([\w_]+)', "admin_pages.AdminProjectsPage"),
    ('/admin/equipment', "admin_pages.AdminEquipmentPage"),
    ('/admin/equipment/([\w_]+)', "admin_pages.AdminEquipmentPage"),
    ('/admin/equipment/([\w_]+)/([\w_\d@\.]+)', "admin_pages.AdminEquipmentPage"),
    ('/admin/equipment/([\w_]+)/([\w_\d@\.]+)/([\w_]+)', "admin_pages.AdminEquipmentPage"),
    ('/admin/equipment/([\w_]+)/([\w_\d@\.]+)/([\w\d_]+)/([\w\d_]+)', "admin_pages.AdminEquipmentPage"),
    ('/admin/calendars', "admin_pages.AdminCalendarPage"),
    ('/admin/calendars/([\w_\d@\.]+)', "admin_pages.AdminCalendarPage"),
    ('/admin/calendars/([\w_\d@\.]+)/([\w\d_]+)', "admin_pages.AdminCalendarPage"),
    ('/admin/calendars/([\w_\d@\.]+)/([\w\d_]+)/([\w\d_]+)', "admin_pages.AdminCalendarPage"),
    ('/admin/feedback', "admin_pages.AdminFeedBackPage"),
    ('/admin/feedback/([\w_]+)', "admin_pages.AdminFeedBackPage"),
    ('/admin/bugs', "admin_pages.AdminBugsPage"),
    ('/admin/bugs/([\w_]+)', "admin_pages.AdminBugsPage"),
    ('/feedback/leave_feedback', "feedback_pages.LeaveFeedBackPage"),
    ('/feedback/report_problem', "feedback_pages.ReportProblemPage"),
    ('/feedback/report_bug', "feedback_pages.ReportBugPage"),
    ('/feedback/view/([\d]+)', "feedback_pages.ViewFeedBackPage"),
    ('/forum', "feedback_pages.ViewForumPage"),
    ('/forum/([\w_]+)', "feedback_pages.ViewForumPage"),
    ('/calendar', "calendar_pages.CalendarPage"),
    ('/calendar/not_connected', "calendar_pages.CalendarNotConnectedPage"),
    ('/calendar/not_visible', "calendar_pages.CalendarNotVisiblePage"),
    ('/calendar/disconnect_account', "calendar_pages.DisconnectCalendarPage"),
    ('/calendar/oauth2callback', "calendar_pages.CalendarOAuth2Page"),
], config=session_config, debug=True)
