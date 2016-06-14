# -*- coding: utf-8 -*-
"""All of the pages used by the application to manage user accounts"""

# standard os library
import os

# cgi library
import cgi

# base pages
import base_pages

# needed to get information about the user
from google.appengine.api import users

# BSB interface
import bsb

def to_bool(string):
    if string == "on":
        return True
    else:
        return False


class DeleteAccountPage(base_pages.BasePostPage):
    """Class that handles the deletion of an account"""

    def needsAccount(self):
        return False

    def _printPage(self, state):
        self.write(state, "delete_account.html", "Delete Account")

    def render_get(self, state):
        self._printPage(state)

    def render_post(self, state):
        pin_number = self.request.get('pin_number', None)

        try:
            bsb.accounts.delete_account(state.user, pin_number)
            self.redirect("/")
        except bsb.accounts.DeleteAccountError as e:
            state.addError(e.message())
            self._printPage(state)

class AccountViewPage(base_pages.BaseGetPage):
    """Simple account viewer page"""

    def render_get(self, state):
        if state.extra_paths is None:
            view_account = state.account
        else:
            view_account = bsb.accounts.get_view_account(state.account, state.extra_paths[0])

        state.setTemplate("view_account", view_account)

        state.setTemplate("equipment_mapping", bsb.equipment.get_equipment_mapping())

        admin_equipment = bsb.equipment.EquipmentACLInfo.getAdministeredEquipment(view_account)
        auth_equipment = bsb.equipment.EquipmentACLInfo.getAuthorisedEquipment(view_account)
        pend_equipment = bsb.equipment.EquipmentACLInfo.getPendingEquipment(view_account)
        band_equipment = bsb.equipment.EquipmentACLInfo.getBannedEquipment(view_account)

        if admin_equipment and len(admin_equipment) > 0:
            state.setTemplate("administered_equipment", admin_equipment)

        if auth_equipment and len(auth_equipment) > 0:
             state.setTemplate("authorised_equipment", auth_equipment)

        if pend_equipment and len(pend_equipment) > 0:
            state.setTemplate("pending_equipment", pend_equipment)

        if band_equipment and len(band_equipment) > 0:
            state.setTemplate("banned_equipment", band_equipment)

        chosen_project = bsb.projects.get_project_by_id(state.account.default_project)
        if chosen_project:
            state.setTemplate("chosen_project", chosen_project)
        
        self.write(state, "view_account.html", "Account | %s" % view_account.email)

class AccountDetailsPage(base_pages.BasePostPage):
    """Class that renders information about the current user's account,
       allowing them to track usage and also update details"""

    def _printPage(self, state):
        if state.account:
            chosen_project = bsb.projects.get_project_by_id(state.account.default_project)
            if chosen_project:
                state.setTemplate("chosen_project", chosen_project)

            state.setTemplate("equipment_mapping", bsb.equipment.get_equipment_mapping())

            admin_equipment = bsb.equipment.EquipmentACLInfo.getAdministeredEquipment(state.account)
            auth_equipment = bsb.equipment.EquipmentACLInfo.getAuthorisedEquipment(state.account)
            pend_equipment = bsb.equipment.EquipmentACLInfo.getPendingEquipment(state.account)
            band_equipment = bsb.equipment.EquipmentACLInfo.getBannedEquipment(state.account)

            if admin_equipment and len(admin_equipment) > 0:
                state.setTemplate("administered_equipment", admin_equipment)

            if auth_equipment and len(auth_equipment) > 0:
                state.setTemplate("authorised_equipment", auth_equipment)

            if pend_equipment and len(pend_equipment) > 0:
                state.setTemplate("pending_equipment", pend_equipment)

            if band_equipment and len(band_equipment) > 0:
                state.setTemplate("banned_equipment", band_equipment)

        self.write(state, "account.html", "Account")

    def render_get(self, state):
      if not state.extra_paths is None:
        if state.extra_paths[0] == "username":
          state.setTemplate("edit_username", True)
        elif state.extra_paths[0] == "project":
          state.setTemplate("edit_project", True)
          projects = bsb.projects.list_projects()
          state.setTemplate('projects', projects)
        elif state.extra_paths[0] == "pin":
          state.setTemplate("edit_pin", True)

      self._printPage(state)

    def render_post(self, state):
      if not state.extra_paths is None:
        if state.extra_paths[0] == "username":
          username = cgi.escape(self.request.get('username', None))

          try:
              bsb.accounts.set_username(state.user, username)
              state.reloadAccountDetails()
          except bsb.accounts.AccountEditError as e:
              state.addErrors(e.errors())

        elif state.extra_paths[0] == "project":
          chosen_project = cgi.escape(self.request.get('chosen_project', None))

          try:
              bsb.accounts.set_default_project(state.user, chosen_project)
              state.reloadAccountDetails()
          except bsb.accounts.AccountEditError as e:
              state.addErrors(e.errors())

        elif state.extra_paths[0] == "pin":
          pin_number = cgi.escape(self.request.get('pin_number', None))

          try:
              bsb.accounts.set_pin_number(state.user, pin_number)
              state.reloadAccountDetails()
          except bsb.accounts.AccountEditError as e:
              state.addErrors(e.errors())  

      self._printPage(state)


class CreateAccountPage(base_pages.BasePostPage):
    """Class that renders the page used to register new BrisSynBio equipment
       user accounts"""

    def needsAccount(self):
        """The create account page does not need an already authenticated account"""
        return False

    def _printPage(self, state, name=None, initials=None, intro_text=None, chosen_project_id=None,
                   check_email=False):

        state.setTemplate("relogin_url", users.create_logout_url(
                                         users.create_login_url(state.current_path)))

        state.setTemplate("enable_popovers", True)

        if check_email:
            email = state.user.email()
            if email.find("@bristol.ac.uk") == -1:
                self.write(state, "check_email.html", "Create Account")
                return

        if initials:
            initials = cgi.escape(initials.upper())
        if name:
            name = cgi.escape(name)
        if intro_text:
            intro_text = cgi.escape(intro_text)

        state.setTemplate('initials', initials)
        state.setTemplate('name', name)
        state.setTemplate('intro_text', intro_text)

        if chosen_project_id:
            project = bsb.projects.get_project_by_id(chosen_project_id)
            state.setTemplate('chosen_project', project)
  
        state.setTemplate('projects', bsb.projects.list_projects())

        self.write(state, "create_account.html", "Create Account")

    def render_get(self, state):
        if state.account:
            self.redirect("/account")
            return

        check_email = to_bool( self.request.get('check_email', "on") )

        self._printPage(state, check_email=check_email)

    def render_post(self, state):
        if state.account:
            self.redirect("/account")
            return

        if not state.user:
            self._printPage(state)
            return

        name = bsb.to_string(self.request.get("name", None))
        initials = bsb.to_string(self.request.get('initials', None))

        intro_text = bsb.to_string(self.request.get('intro_text', None).lstrip().rstrip())

        chosen_project = bsb.to_string(self.request.get('chosen_project', None))

        if chosen_project == "None":
            chosen_project = None

        try:
            bsb.accounts.add_account(state.user, name, initials, intro_text, chosen_project)
            self.redirect("/account")
        except bsb.accounts.AddAccountError as e:
            state.addErrors(e.errors())
            self._printPage(state, name, initials, intro_text, chosen_project)
