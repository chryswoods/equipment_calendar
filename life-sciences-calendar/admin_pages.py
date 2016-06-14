# -*- coding: utf-8 -*-
"""All of the pages used by the application to administer the site"""

# base pages
import base_pages

# CGI interface
import cgi

# pickling
import pickle

# dates and times
import datetime

# BSB interface
import bsb

main_menu_items = [ base_pages.MenuItem("summary", "/admin/summary"),
                    base_pages.MenuItem("equipment", "/admin/equipment"),
                    base_pages.MenuItem("users", "/admin/users"),
                    base_pages.MenuItem("projects", "/admin/projects"),
                    base_pages.MenuItem("feedback", "/admin/feedback"),
                    base_pages.MenuItem("bugs", "/admin/bugs"),
                    base_pages.MenuItem("backup", "/admin/backup") ]

equipment_menu_items = [ base_pages.MenuItem("summary", "/admin/summary"),
                         base_pages.MenuItem("equipment", "/admin/equipment"),
                         base_pages.MenuItem("equipment types", "/admin/equipment/types"),
                         base_pages.MenuItem("laboratories", "/admin/equipment/labs"),
                         base_pages.MenuItem("calendars", "/admin/calendars"),
                         base_pages.MenuItem("bookings", "/admin/equipment/bookings") ]

def to_bool(string):
    if string == "on":
        return True
    else:
        return False

class AdminPage(base_pages.BasePostPage):
    """Class that handles the main administration page"""

    def safeInMaintenanceMode(self):
        """Return whether or not this page should be viewable even
           if maintenance mode is switched on"""
        return True

    def needsAdmin(self):
        return True

    def _printPage(self, state):
        state.addParentPage("/admin")
        state.addParentPage("/admin/summary")
        state = self.buildSubMenu(state, main_menu_items)

        state.setTemplate("number_of_accounts", bsb.accounts.number_of_accounts())
        state.setTemplate("number_to_approve", bsb.accounts.number_of_account_to_approve())
        state.setTemplate("number_of_projects", bsb.projects.number_of_projects())

        management_tasks = []

        if bsb.accounts.number_of_account_to_approve() > 0:
            management_tasks.append( ("You have some user accounts to approve.",
                                      "/admin/users") )


        has_calendar_account = bsb.calendar.hasCalendarAccount()
        state.setTemplate("has_calendar_account", has_calendar_account)

        if not has_calendar_account:
            management_tasks.append( ("You have to connect the calendar account.",
                                      bsb.calendar.connectCalendarAccountURL()) )

        if len(management_tasks) > 0:
            state.setTemplate("management_tasks", management_tasks)

        if has_calendar_account:
            state.setTemplate("calendar_url", bsb.calendar.disconnectCalendarAccountURL())
        else:
            # provide a link to the calendar, and set a session key so that any
            # login attempt can be verified as originating from this page
            session_key = self.createSessionKey()
            state.setTemplate("calendar_url", bsb.calendar.connectCalendarAccountURL(session_key))

        self.write(state, "admin.html", "Admin")

    def render_get(self, state):
        self._printPage(state)

    def render_post(self, state):

        maintenance_state = to_bool( self.request.get('switch_maintenance', None) )
        bsb.admin.set_maintenance_state(maintenance_state)

        state.setTemplate("under_maintenance", maintenance_state)

        self._printPage(state)

databases = { "Account" : bsb.accounts.AccountInfo,
              "Calendar" : bsb.calendar.CalendarInfo,
              "Equipment" : bsb.equipment.EquipmentInfo,
              "EquipmentType" : bsb.equipment.EquipmentTypeInfo,
              "Laboratory" : bsb.equipment.LaboratoryInfo,
              "Project" : bsb.projects.ProjectInfo }

class BackupPage(base_pages.BasePostPage):
    """Page used to control the backup and restore of the databases"""

    def needsAdmin(self):
        return True

    def render_restore(self, state, is_post):
        if is_post and len(state.extra_paths) > 1:
            database = state.extra_paths[1]
            file_contents = self.request.POST.multi["filecontents"].file.read()

            if database == "all":
                backups = pickle.loads(file_contents)

                failures = {}

                for backup in backups:
                    try:
                        databases[backup].restore(state.account, backups[backup])
                    except Exception as e:
                        failures[backup] = e
        
                if len(failures) > 0:
                    raise bsb.InputError("Cannot restore fully from backup file! See details for more information.",
                                         detail=failures)
            else:
                try:
                    databases[database].restore(state.account, file_contents)
                except Exception as e:
                    raise bsb.InputError("Cannot restore the backup for database '%s'." % database,
                                         detail=e)

        self.redirect("/admin/backup")            

    def render_backup(self, state, is_post):
        if len(state.extra_paths) > 1:
            database = state.extra_paths[1]
            filename = self.request.get("filename", "backup.dat")

            output = None

            if database == "all":
                backups = {}
                for db in databases:
                    backups[db] = databases[db].backup(state.account)

                output = pickle.dumps(backups)
            else:
                output = databases[database].backup(state.account)

        self.response.clear()
        self.response.content_type = "application/octet-stream"
        self.response.headers = { "Content-Type" : "application/octet-stream",
                                  "Content-Disposition" : "inline; filename=\"%s\"" % str(filename)}
        self.response.write(output)

    def render_delete(self, state, is_post):
        if len(state.extra_paths) > 2:
            database = state.extra_paths[1]
            action = state.extra_paths[2]

            if action == "delete":
                state.setTemplate("really_delete", database)
            elif action == "really_delete":
                if database == "all":
                    for db in databases:
                        databases[db].deleteDB(state.account)

                    state.addMessage("Cleared all databases!")
                else:
                    if database in databases:
                        databases[database].deleteDB(state.account)
                        state.addMessage("Cleared database '%s'!" % database)

        return self.render_overview(state, is_post)

    def render_view(self, state, is_post):
        if len(state.extra_paths) > 1:
            database = state.extra_paths[1]

            if database in databases:
                state.setTemplate("data", databases[database].getAll(state.account))
                state.setTemplate("database", database)
                self.write(state, "admin_backup_backup.html", "Admin | Backup | %s" % database)
                return
        
        self.redirect("/admin/backup")

    def render_overview(self, state, is_post):
        keys = list(databases.keys())
        keys.sort()
        state.setTemplate("databases", keys)
        self.write(state, "admin_backup_overview.html", "Admin | Backup/Restore")

    def render_post(self, state, is_post=True):
        state.addParentPage("/admin/backup")
        state.addParentPage("/admin")
        state = self.buildSubMenu(state, main_menu_items)

        if state.extra_paths is None:
            return self.render_overview(state, is_post)
        else:
            if state.extra_paths[0] == "backup":
                return self.render_backup(state, is_post)
            elif state.extra_paths[0] == "restore":
                return self.render_restore(state, is_post)
            elif state.extra_paths[0] == "view":
                return self.render_view(state, is_post)
            elif state.extra_paths[0] == "delete":
                return self.render_delete(state, is_post)
            else:
                state.addError("Cannot recognised action '%s'" % state.extra_paths[0])
                return self.render_overview(state, is_post)

    def render_get(self, state):
        self.render_post(state, False)

class AdminProjectsPage(base_pages.BasePostPage):
    """Class that can be used to administer projects"""

    def needsAdmin(self):
        return True

    def _printOverview(self, state):
        projects = bsb.projects.list_projects()
        state.setTemplate('projects', projects)
        self.write(state, "admin_projects.html", "Admin Projects")

    def _printView(self, state, project_id):
        project = bsb.projects.get_project_by_id(project_id)

        if project:
            state.setTemplate("project", project)
            self.write(state, "admin_projects_view.html", "Admin Users | View | %s" % project.title)
        else:
            state.addError("No project associated with ID '%s'" % id)
            self._printOverview(state)        

    def _deleteProject(self, state, project_id, really_delete=False):
        if really_delete:
            try:
                project = bsb.projects.delete_project(state.account, project_id)
            except bsb.projects.DeleteProjectError as e:
                state.addError(e.error())

        else:
            state.setTemplate("really_delete", project_id)

        self._printOverview(state)

    def render_get(self, state):
        state.addParentPage("/admin/projects")
        state.addParentPage("/admin")
        state = self.buildSubMenu(state, main_menu_items)

        if state.extra_paths is None:
            self._printOverview(state)
        else:
            if state.extra_paths[0] == "view":
                self._printView(state, state.extra_paths[1])
            elif state.extra_paths[0] == "delete":
                self._deleteProject(state, state.extra_paths[1])
            elif state.extra_paths[0] == "really_delete":
                self._deleteProject(state, state.extra_paths[1], True)
            else:
                state.addError("Unrecognised action '%s'" % state.extra_paths[0])
                self._printOverview(state)
    
    def render_post(self, state):

        if state.extra_paths is None:
            self.render_get(state)
        else:
            if state.extra_paths[0] == "create":
                state.addParentPage("/admin/projects")
                state.addParentPage("/admin")
                state = self.buildSubMenu(state, main_menu_items)

                # get the details about the project to create from the form
                project_title = cgi.escape(self.request.get('project_title', None))
                bsb_project = to_bool( self.request.get('bsb_project', None) )
                vat_exempt = to_bool( self.request.get('vat_exempt', None) )

                try:
                    bsb.projects.add_project(state.account, project_title, bsb_project, vat_exempt)

                except bsb.projects.AddProjectError as e:
                    state.addErrors(e.errors())

                self._printOverview(state)

            else:
                self.render_get(state)

class AdminUsersPage(base_pages.BaseGetPage):
    """Class that can be used to administer users"""

    def needsAdmin(self):
        return True

    def _printOverview(self, state):
        accounts = bsb.accounts.list_accounts()
        state.setTemplate('accounts', accounts)
        self.write(state, "admin_users.html", "Admin Users")    

    def _printView(self, state, email):
        view_account = bsb.accounts.get_account_by_email(state.account, email)

        if view_account:
            state.setTemplate("view_account", view_account)
            self.write(state, "admin_users_view.html", "Admin Users | View | %s" % email)
        else:
            state.addError("No account associated with email '%s'" % email)
            self._printOverview(state)        

    def _approveAccount(self, state, email):
        try:
            bsb.accounts.approve_account(state.account, email)
            self.redirect("/admin/users")
            return
        except bsb.accounts.AccountPermissionError as e:
            state.addErrors(e.errors())
            self._printOverview(state)

    def _makeAdminAccount(self, state, email):
        try:
            bsb.accounts.make_admin_account(state.account, email)
            self.redirect("/admin/users")
            return
        except bsb.accounts.AccountPermissionError as e:
            state.addErrors(e.errors())
            self._printOverview(state)

    def _revokeAdminAccess(self, state, email):
        try:
            bsb.accounts.revoke_admin_access(state.account, email)
            self.redirect("/admin/users")
            return
        except bsb.accounts.AccountPermissionError as e:
            state.addErrors(e.errors())
            self._printOverview(state)

    def _revokeAccess(self, state, email):
        try:
            bsb.accounts.revoke_access(state.account, email)
            self.redirect("/admin/users")
            return
        except bsb.accounts.AccountPermissionError as e:
            state.addErrors(e.errors())
            self._printOverview(state)

    def render_get(self, state):
        state.addParentPage("/admin/users")
        state.addParentPage("/admin")
        state = self.buildSubMenu(state, main_menu_items)

        if state.extra_paths is None:
            self._printOverview(state)
        else:
            if state.extra_paths[0] == "view":
                self._printView(state, state.extra_paths[1])
            elif state.extra_paths[0] == "approve":
                self._approveAccount(state, state.extra_paths[1])
            elif state.extra_paths[0] == "grant_admin":
                self._makeAdminAccount(state, state.extra_paths[1])
            elif state.extra_paths[0] == "revoke_admin":
                self._revokeAdminAccess(state, state.extra_paths[1])
            elif state.extra_paths[0] == "revoke_access":
                self._revokeAccess(state, state.extra_paths[1])
            else:
                state.addError("Unrecognised action '%s'" % state.extra_paths[0])
                self._printOverview(state)

class AdminCalendarPage(base_pages.BasePostPage):
    """Class that can be used to administer the calendars attached to the site"""

    def needsAdmin(self):
        return True

    def calendarViewPage(self, state, idstring, action, is_post=False):
        """Admin view of an individual calendar"""

        calendar = bsb.calendar.get_calendar(state.account,idstring)

        if calendar is None:
            state.addError("There is no calendar associated with IDString '%s'." % idstring)
            self.calendarsPage(state)
            return

        if is_post:
            try:
                sub_action = state.extra_paths[2]
            except:
                sub_action = ""

            if action == "edit_viewers":
                viewers = bsb.processListEdit(self, "viewer", sub_action)
                calendar.setViewers(state.account, viewers)
            elif action == "edit_admin":
                is_admin = bsb.processBoolEdit(self, "needs_admin")
                calendar.setNeedsAdmin(is_admin)
            elif action == "edit_info":
                info = bsb.processDictionaryEdit(self, "information", sub_action)
                calendar.setInformation(state.account, info)
            else:
                raise bsb.InputError("""Unknown form action '%s' for calendar '%s'.""" % (action,calendar.name))

            self.redirect("/admin/calendars/%s" % idstring)
        else:
            if action == "delete":
                state.setTemplate("really_delete", idstring)
                self.calendarsPage(state, False)
                return

            elif action == "really_delete":
                # we really want to delete this calendar - this is likely to cause problems elsewhere, buy hey-ho
                bsb.calendar.delete_calendar(state.account, idstring)
                state.addMessage("Deleted calendar '%s'" % calendar.name)
                self.calendarsPage(state, False)
                return

            elif action in ["edit_viewers", "edit_admin", "edit_info"]:
                state.setTemplate(action, True)

            elif action == "connect":
                calendar.connect(state.account)
                self.redirect("/admin/calendars/%s" % idstring)

            elif action == "disconnect":
                state.setTemplate("really_disconnect", True)

            elif action == "really_disconnect":
                calendar.disconnect(state.account)
                self.redirect("/admin/calendars/%s" % idstring)

            elif action:
                raise bsb.InputError("""Unknown form action '%s' for calendar '%s'.""" % (action,calendar.name))           

        state.setTemplate("calendar", calendar)
        state.setTemplate("calendar_url", calendar.getURL(state.account))
        self.write(state, "admin_calendars_view.html", "Admin | Calendar | %s" % calendar.name)

    def calendarsPage(self, state, is_post=False):
        """Admin view of the list of calendars"""
        if is_post:
            # we are trying to add a new calendar - get the information from the page
            calendar_name = self.request.get('calendar_name', None)       
            new_calendar = bsb.calendar.add_calendar(state.account, calendar_name)

            if new_calendar:
                state.addMessage("Added the new calendar '%s'. Click on it to edit it further." % calendar_name)

        calendars = bsb.calendar.list_calendars()

        urls = []
        for calendar in calendars:
            urls.append( calendar.getURL(state.account) )

        state.setTemplate('calendars', calendars)
        state.setTemplate('urls', urls)

        self.write(state, "admin_calendars.html", "Admin Calendars")    

    def render_get(self, state):
        self.render_post(state, False)

    def render_post(self, state, is_post=True):
        state.addParentPage("/admin/calendars")
        state.addParentPage("/admin")
        state = self.buildSubMenu(state, equipment_menu_items)

        if state.extra_paths is None:
            self.calendarsPage(state, is_post)
        else:
            if len(state.extra_paths) > 1:
                self.calendarViewPage(state, state.extra_paths[0], state.extra_paths[1], is_post)
            else:
                self.calendarViewPage(state, state.extra_paths[0], None, is_post)


class AdminEquipmentPage(base_pages.BasePostPage):
    """Class that can be used to administer the equipment"""

    def needsAdmin(self):
        return True

    def labPage(self, state, idstring, action, is_post):
        """Admin view of an individual lab"""

        lab = bsb.equipment.get_laboratory(idstring)
    
        if lab is None:
             state.addError("There is no laboratory associated with the IDString '%s'." % idstring)
             self.labsPage(state)
             return
        
        if is_post:
            try:
                sub_action = state.extra_paths[3]
            except:
                sub_action = ""

            if action == "edit_owners":
                owners = bsb.processListEdit(self, "owner", sub_action)
                lab.setOwners(state.account, owners)
            elif action == "edit_location":
                location = bsb.processLocationEdit(self, "location", sub_action)
                lab.setLocation(state.account, location)
            elif action == "edit_info":
                info = bsb.processDictionaryEdit(self, "information", sub_action)
                lab.setInformation(state.account, info)
            else:
                raise bsb.InputError("""Unknown form action '%s' for lab '%s'.""" % (action,lab.name))

            self.redirect("/admin/equipment/labs/%s" % idstring)

        else:
            if action == "delete":
                state.setTemplate("really_delete", idstring)
                self.labsPage(state, False)
                return

            elif action == "really_delete":
                # we really want to delete this lab
                bsb.equipment.delete_laboratory(state.account, idstring)
                state.addMessage("Deleted laboratory '%s'" % lab.name)
                self.labsPage(state, False)
                return

            elif action in ["edit_owners", "edit_location", "edit_info"]:
                state.setTemplate(action, True)

            elif action:
                raise bsb.InputError("""Unknown form action '%s' for lab '%s'.""" % (action,lab.name))

            state.setTemplate("lab", lab)
            self.write(state, "admin_labs_view.html", "Admin Lab | %s" % lab.name)

    def labsPage(self, state, is_post=False):
        """Overview page for all of the labs"""
        if is_post:
            # we are trying to add a new lab - get the information from the page
            lab_name = self.request.get('lab_name', None)
            lab_owners = self.request.get("lab_owners", None)
            
            new_lab = bsb.equipment.add_laboratory(state.account, lab_name, lab_owners)

            if new_lab:
                state.addMessage("Added the new laboratory '%s'. Click on it to edit it further." % lab_name)

        labs = bsb.equipment.list_laboratories()
        state.setTemplate('labs', labs)

        self.write(state, "admin_labs.html", "Admin Labs")    

    def typesPage(self, state, is_post=False):
        """Overview page for all of the equipment types"""
        if is_post:
            # we are trying to add a new equipment type - get the information from the page
            type_name = self.request.get('type_name', None)
            
            new_type = bsb.equipment.add_equipment_type(state.account, type_name)

            if new_type:
                state.addMessage("Added new equipment type '%s'. Click on it to edit it further." % type_name)

        types = bsb.equipment.list_equipment_types()
        state.setTemplate("types", types)

        self.write(state, "admin_types.html", "Admin Equipment Types")

    def typeViewPage(self, state, idstring, action, is_post):
        """Admin view of an individual equipment type"""
        type = bsb.equipment.get_equipment_type(idstring)
    
        if type is None:
             state.addError("There is no equipment type associated with the IDString '%s'." % idstring)
             self.typesPage(state)
             return
        
        if is_post:
            try:
                sub_action = state.extra_paths[3]
            except:
                sub_action = ""

            if action == "edit_info":
                info = bsb.processDictionaryEdit(self, "information", sub_action)
                type.setInformation(state.account, info)
            else:
                raise bsb.InputError("""Unknown form action '%s' for equipment type '%s'.""" % (action,type.name))

            self.redirect("/admin/equipment/types/%s" % idstring)

        else:
            if action == "delete":
                state.setTemplate("really_delete", idstring)
                self.typesPage(state, False)
                return

            elif action == "really_delete":
                # we really want to delete this lab
                bsb.equipment.delete_equipment_type(state.account, idstring)
                state.addMessage("Deleted equipment type '%s'" % type.name)
                self.typesPage(state, False)
                return

            elif action in ["edit_info"]:
                state.setTemplate(action, True)

            elif action:
                raise bsb.InputError("""Unknown form action '%s' for equipment type '%s'.""" % (action,type.name))

            state.setTemplate("equipment_type", type)
            self.write(state, "admin_types_view.html", "Admin Equipment Type | %s" % type.name)

    def bookingsPage(self, state, is_post):
        """Overview page for all of the equipment bookings"""
        if is_post:
            # we are trying to modify or add a booking
            raise bsb.IncompleteCodeError()

        now_time = bsb.get_now_time()
        today_start = datetime.datetime(now_time.year, now_time.month, now_time.day)

        old_range_start = bsb.to_date(self.request.get("range_start"))
        old_range_end = bsb.to_date(self.request.get("range_end"))

        if old_range_start and old_range_end:
            if old_range_start > old_range_end:
                tmp = old_range_start
                old_range_start = old_range_end
                old_range_end = tmp

        if not old_range_start:
            old_range_start = today_start
            old_range_end = today_start + datetime.timedelta(days=7)
        elif not old_range_end:
            old_range_end = today_start + datetime.timedelta(days=7)

        state.setTemplate("today_start", today_start)

        state.setTemplate("range_start", old_range_start)
        state.setTemplate("range_end", old_range_end)

        state.setTemplate("older_range_start", old_range_start - datetime.timedelta(days=7))
        state.setTemplate("older_range_end", old_range_start)

        state.setTemplate("newer_range_start", old_range_end)
        state.setTemplate("newer_range_end", old_range_end + datetime.timedelta(days=7))

        bookings = bsb.equipment.get_bookings(start_time=old_range_start, end_time=old_range_end)
        state.setTemplate("bookings", bookings)
        state.setTemplate("account_mapping", bsb.accounts.get_account_mapping())

        self.write(state, "admin_bookings.html", "Admin Bookings")

    def bookingPage(self, state, idstring, action, is_post):
        """Admin view of an individual booking"""
        booking = bsb.equipment.get_booking(idstring)
    
        if booking is None:
             state.addError("There is no booking associated with the IDString '%s'." % idstring)
             self.bookingsPage(state)
             return
        
        state.setTemplate("booking", booking)
        self.write(state, "admin_bookings_view.html", "Admin Booking")

    def equipmentPage(self, state, is_post=False):
        """Overview page for all of the equipment in the system"""
        if is_post:
            item_name = bsb.to_string( self.request.get("item_name", None) )
            item_type = bsb.to_string( self.request.get("item_type", None) )
            item_lab = bsb.to_string( self.request.get("item_lab", None) )

            ok = True

            if item_name is None:
                state.addError("You must specify the name of the new piece of equipment.")
                ok = False

            if item_type is None:
                state.addError("You must choose the type of the new piece of equipment.")
                ok = False

            if item_lab is None:
                state.addError("You must choose a laboratory for the new piece of equipment.")
                ok = False

            if ok:
                new_item = bsb.equipment.add_equipment(state.account, item_name, item_type, item_lab)

                if new_item:
                    state.addMessage("Added new equipment item '%s'. Click on it to edit it further." % item_name)

        state.setTemplate("labs", bsb.equipment.get_sorted_laboratory_mapping())
        state.setTemplate("equipment_types", bsb.equipment.get_sorted_equipment_type_mapping())
        state.setTemplate("labs_dict", bsb.equipment.get_laboratory_mapping())
        state.setTemplate("types_dict", bsb.equipment.get_equipment_type_mapping())

        state.setTemplate("equipment", bsb.equipment.list_equipment())

        self.write(state, "admin_equipment.html", "Admin Equipment")        

    def equipmentViewPage(self, state, idstring, action, is_post):
        """Admin view of an individual piece of equipment"""
        item = bsb.equipment.get_equipment(idstring)
    
        if item is None:
             state.addError("There is no piece of equipment associated with the IDString '%s'." % idstring)
             self.equipmentPage(state)
             return

        state.setTemplate( "banned", item.getBannedUsers(state.account) )
        state.setTemplate( "pending", item.getPendingUsers(state.account) )
        state.setTemplate( "authorised", item.getAuthorisedUsers(state.account) )
        state.setTemplate( "administrators", item.getAdministratorUsers(state.account) )

        if is_post:
            try:
                sub_action = state.extra_paths[3]
            except:
                sub_action = ""

            if action == "edit_info":
                info = bsb.processDictionaryEdit(self, "information", sub_action)
                item.setInformation(state.account, info)
            elif action == "edit_administrators":
                emails = bsb.processListEdit(self, "administrators", sub_action)
                item.setAdministratorUsers(state.account, emails)
            elif action == "edit_authorised":
                emails = bsb.processListEdit(self, "authorised", sub_action)
                item.setAuthorisedUsers(state.account, emails)
            elif action == "edit_pending":
                emails = bsb.processListEdit(self, "pending", sub_action)
                item.setPendingUsers(state.account, emails)
            elif action == "edit_banned":
                emails = bsb.processListEdit(self, "banned", sub_action)
                item.setBannedUsers(state.account, emails)
            else:
                raise bsb.InputError("""Unknown form action '%s' for equipment item '%s'.""" % (action,item.name))

            self.redirect("/admin/equipment/item/%s" % idstring)

        else:
            if action == "delete":
                state.setTemplate("really_delete", idstring)
                self.equipmentPage(state, False)
                return

            elif action == "really_delete":
                # we really want to delete this piece of equipment
                bsb.equipment.delete_equipment(state.account, idstring)
                state.addMessage("Deleted equipment item '%s'" % item.name)
                self.equipmentPage(state, False)
                return

            elif action in ["edit_info", "edit_administrators", "edit_pending", "edit_banned", "edit_authorised"]:
                state.setTemplate(action, True)

            elif action == "create_calendar":
                # create the calendar for this item
                cal = item.createCalendar(state.account)

                if cal:
                    state.addMessage("Created calendar '%s' for equipment item '%s'" % (cal.name,item.name))
                else:
                    state.addError("Failed to create a calendar for equipment item '%s'" % item.name)

            elif action:
                raise bsb.InputError("""Unknown form action '%s' for equipment item '%s'.""" % (action,item.name))

            state.setTemplate("equipment_item", item)
            state.setTemplate("equipment_type", bsb.equipment.get_equipment_type(item.equipment_type))
            state.setTemplate("lab", bsb.equipment.get_laboratory(item.laboratory))
            state.setTemplate("calendar", bsb.calendar.get_calendar(state.account, item.calendar))

            self.write(state, "admin_equipment_view.html", "Admin Equipment | %s" % item.name)

    def overviewPage(self, state, is_post):
        self.equipmentPage(state, is_post)

    def render_get(self, state):
        self.render_post(state, False)

    def render_post(self, state, is_post=True):
        state.addParentPage("/admin")

        if state.extra_paths and state.extra_paths[0] in ["labs", "types", "bookings"]:
            state.addParentPage("/admin/equipment/%s" % state.extra_paths[0])
        else:
            state.addParentPage("/admin/equipment")

        state = self.buildSubMenu(state, equipment_menu_items)

        if state.extra_paths is None:
            self.overviewPage(state, is_post)
        else:
            if state.extra_paths[0] == "item":
                if len(state.extra_paths) > 2:
                    self.equipmentViewPage(state, state.extra_paths[1], state.extra_paths[2], is_post)
                elif len(state.extra_paths) > 1:
                    self.equipmentViewPage(state, state.extra_paths[1], None, is_post)
                else:
                    self.equipmentPage(state, is_post)
            elif state.extra_paths[0] == "labs":
                if len(state.extra_paths) > 2:
                    self.labPage(state, state.extra_paths[1], state.extra_paths[2], is_post)
                elif len(state.extra_paths) > 1:
                    self.labPage(state, state.extra_paths[1], None, is_post)
                else:
                    self.labsPage(state, is_post)

            elif state.extra_paths[0] == "types":
                if len(state.extra_paths) > 2:
                    self.typeViewPage(state, state.extra_paths[1], state.extra_paths[2], is_post)
                elif len(state.extra_paths) > 1:
                    self.typeViewPage(state, state.extra_paths[1], None, is_post)
                else:
                    self.typesPage(state, is_post)
            elif state.extra_paths[0] == "bookings":
                if len(state.extra_paths) > 2:
                    self.bookingPage(state, state.extra_paths[1], state.extra_paths[2], is_post)
                elif len(state.extra_paths) > 1:
                    self.bookingPage(state, state.extra_paths[1], None, is_post)
                else:
                    self.bookingsPage(state, is_post)
            else:
                state.addError("Unrecognised action '%s'" % state.extra_paths[0])
                self.overviewPage(state, is_post)

class AdminBugsPage(base_pages.BasePostPage):
    """Class to view the bugs pages"""
    def needsAdmin(self):
        return True

    def render_get(self, state):
        self.render_post(state, False)

    def overviewPage(self, state, is_post):
        now_time = bsb.get_now_time()
        today_start = bsb.get_day_from(now_time)

        old_range_start = bsb.to_date(self.request.get("range_start"))
        old_range_end = bsb.to_date(self.request.get("range_end"))

        if old_range_start and old_range_end:
            if old_range_start > old_range_end:
                tmp = old_range_start
                old_range_start = old_range_end
                old_range_end = tmp

            if old_range_start > now_time:
                old_range_start = None
                old_range_end = None
            elif old_range_end > today_start: 
                old_range_end = today_start

        if not old_range_start:
            old_range_start = today_start - datetime.timedelta(days=7)
            old_range_end = today_start
        elif not old_range_end:
            old_range_end = today_start

        view_user = bsb.to_string(self.request.get("view_user",None))

        if not view_user:
            view_user = "all"

        state.setTemplate("today_start", today_start)

        state.setTemplate("range_start", old_range_start)
        state.setTemplate("range_end", old_range_end)

        state.setTemplate("older_range_start", old_range_start - datetime.timedelta(days=7))
        state.setTemplate("older_range_end", old_range_start)

        state.setTemplate("newer_range_start", old_range_end)
        state.setTemplate("newer_range_end", min(today_start, old_range_end + datetime.timedelta(days=7)))

        state.setTemplate("view_user", view_user)

        state.setTemplate("really_delete", bsb.to_int(self.request.get("really_delete")))

        state.setTemplate("bugs", bsb.feedback.get_bugs(state.account, old_range_start, 
                                                        old_range_end + datetime.timedelta(days=1), view_user))
 
        self.write(state, "admin_bugs.html", "Admin | Bugs")

    def deleteBugs(self, state, is_post):
        if is_post:
            bug_ids = self.request.get_all("bugbox",[])
            bsb.feedback.BugInfo.deleteBugs(state.account, bug_ids)

        self.redirect("/admin/bugs")                    

    def deleteBug(self, state, is_post):
        bug_id = bsb.to_int(self.request.get("bug_id",None))

        if bug_id:
            bug = bsb.feedback.BugInfo(bug_id=bug_id)
            bug.deleteBug(state.account)

        self.redirect("/admin/bugs")

    def render_post(self, state, is_post=True):
        state.addParentPage("/admin")
        state.addParentPage("/bugs")
        state = self.buildSubMenu(state, main_menu_items)

        if state.extra_paths:
            if state.extra_paths[0] == "delete_bug":
                return self.deleteBug(state, is_post)
            elif state.extra_paths[0] == "delete_bugs":
                return self.deleteBugs(state, is_post)
            else:
                state.addError("Unknown action '%s'" % state.extra_paths[0])

        state.setTemplate("account_mapping", bsb.accounts.get_account_mapping())

        self.overviewPage(state, is_post)

class AdminFeedBackPage(base_pages.BasePostPage):
    """Class to view the feedback and bugs pages"""
    def needsAdmin(self):
        return True

    def render_get(self, state):
        self.render_post(state, False)

    def overviewPage(self, state, is_post):
        now_time = bsb.get_now_time()
        today_start = datetime.datetime(now_time.year, now_time.month, now_time.day)

        old_range_start = bsb.to_date(self.request.get("range_start"))
        old_range_end = bsb.to_date(self.request.get("range_end"))

        if old_range_start and old_range_end:
            if old_range_start > old_range_end:
                tmp = old_range_start
                old_range_start = old_range_end
                old_range_end = tmp

            if old_range_start > now_time:
                old_range_start = None
                old_range_end = None
            elif old_range_end > today_start: 
                old_range_end = today_start

        if not old_range_start:
            old_range_start = today_start - datetime.timedelta(days=7)
            old_range_end = today_start
        elif not old_range_end:
            old_range_end = today_start

        state.setTemplate("today_start", today_start)

        state.setTemplate("range_start", old_range_start)
        state.setTemplate("range_end", old_range_end)

        state.setTemplate("older_range_start", old_range_start - datetime.timedelta(days=7))
        state.setTemplate("older_range_end", old_range_start)

        state.setTemplate("newer_range_start", old_range_end)
        state.setTemplate("newer_range_end", min(today_start, old_range_end + datetime.timedelta(days=7)))

        state.setTemplate("feedback", bsb.feedback.get_feedback(state.account, old_range_start, 
                                                                old_range_end + datetime.timedelta(days=1)))
 
        self.write(state, "admin_feedback.html", "Admin | Feedback")

    def deleteFeedBacks(self, state, is_post):
        if is_post:
            feedback_ids = self.request.get_all("feedback_box",[])
            bsb.feedback.FeedBackInfo.deleteFeedBacks(state.account, feedback_ids)

        self.redirect("/admin/feedback")                    

    def deleteFeedBack(self, state, is_post):
        feedback_id = bsb.to_int(self.request.get("feedback_id",None))

        if feedback_id:
            feedback = bsb.feedback.FeedBackInfo(feedback_id=feedback_id)
            feedback.deleteFeedBack(state.account)

        self.redirect("/admin/feedback")

    def render_post(self, state, is_post=True):
        state.addParentPage("/admin")
        state.addParentPage("/feedback")
        state = self.buildSubMenu(state, main_menu_items)

        if state.extra_paths:
            if state.extra_paths[0] == "delete_feedback":
                return self.deleteFeedBack(state, is_post)
            elif state.extra_paths[0] == "delete_feedbacks":
                return self.deleteFeedBacks(state, is_post)
            else:
                state.addError("Unknown action '%s'" % state.extra_paths[0])

        state.setTemplate("account_mapping", bsb.accounts.get_account_mapping())

        self.overviewPage(state, is_post)
