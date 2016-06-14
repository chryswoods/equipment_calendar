# -*- coding: utf-8 -*-
"""All of the pages used by the application to manage and schedule equipment"""

# base pages
import base_pages

# datetime interface
import datetime

# BSB interface
import bsb

#main_menu_items = [ base_pages.MenuItem("summary", "/equipment/summary"),
#                    base_pages.MenuItem("bookings", "/equipment/bookings"),
#                    base_pages.MenuItem("laboratories", "/equipment/labs"),
#                    base_pages.MenuItem("equipment types", "/equipment/types"),
#                    base_pages.MenuItem("map", "/equipment/map")  ]

class EquipmentPage(base_pages.BasePostPage):
    """Class that handles the main equipment page"""

    def labsPage(self, state, lab, is_post):
        lab = bsb.to_string(lab)

        if not lab:
            return self.redirect("/equipment/laboratories")

        laboratory = bsb.equipment.get_laboratory(lab)

        if not laboratory:
            state.addError("Cannot find laboratory with ID string '%s'" % lab)
            return self.browsePage(state, False, is_post)

        state.setTemplate("laboratory", laboratory)
        state.setTemplate("equipment", bsb.equipment.get_sorted_equipment_for_account(state.account))
        state.setTemplate("equip", bsb.equipment.list_equipment_in_laboratory(laboratory))

        self.write(state, "view_lab.html", "Equipment | %s" % laboratory.name)

    def typesPage(self, state, equip_type, is_post):
        equip_type = bsb.to_string(equip_type)

        if not equip_type:
            return self.redirect("/equipment/types")

        equiptype = bsb.equipment.get_equipment_type(equip_type)

        if not equiptype:
            state.addError("Cannot find equipment type with ID string '%s'" % equip_type)
            return self.browsePage(state, True, is_post)

        state.setTemplate("equip_type", equiptype)
        state.setTemplate("equipment", bsb.equipment.get_sorted_equipment_for_account(state.account))
        state.setTemplate("equip", bsb.equipment.list_equipment_with_type(equiptype))
        state.setTemplate("lab_mapping", bsb.equipment.get_laboratory_mapping())

        self.write(state, "view_type.html", "Equipment | %s" % equiptype.name)

    def browsePage(self, state, sort_by_type, is_post):
        state.setTemplate("sort_by_type", sort_by_type)
        state.setTemplate("equipment", bsb.equipment.get_sorted_equipment_for_account(state.account))

        if sort_by_type:
            state.setTemplate("equip", bsb.equipment.list_equipment_by_type())
        else:
            state.setTemplate("equip", bsb.equipment.list_equipment_by_laboratory())

        state.setTemplate("type_mapping", bsb.equipment.get_equipment_type_mapping())
        state.setTemplate("lab_mapping", bsb.equipment.get_laboratory_mapping())

        self.write(state, "browse_equipment.html", "Equipment | Browse...")

    def overviewPage(self, state, is_post):
        state.setTemplate("equipment", bsb.equipment.get_sorted_equipment_for_account(state.account))
        state.setTemplate("equipment_mapping", bsb.equipment.get_equipment_mapping())
        self.write(state, "equipment.html", "Equipment")

    def _itemCalendarPage(self, state, item, acl, is_demo=False):
        if acl:
            if acl.isAuthorised():
                calendar = item.getCalendar(state.account)
                state.setTemplate("item", item) 
                state.setTemplate("calendar", calendar)

                calendar_type = "week"

                if item.constraints:
                    calendar_type = item.constraints.calendarType()
                
                state.setTemplate("calendar_html", calendar.getEmbedHTML(state.account, 
                                                                         calendar_type=calendar_type))

        if is_demo:
            state.setTemplate("is_demo", True)

        self.write(state, "view_equipment.html", "Equipment | %s" % item.name)

    def itemBookingPage(self, state, item, acl, is_post):
        if not acl.isAuthorised():
            state.addError("You do not have permission to use this piece of equipment")
            return self.itemPage(state, item.idstring, is_post)

        state.setTemplate("enable_popovers", True)

        action = self.request.get("booking_action", None)
        
        if not action:
            action = "start_booking"

        if action == "start_booking":
            start_time = self.request.get("start_time", None)
            end_time = self.request.get("end_time", None)

            start_time = bsb.to_datetime(start_time)
            end_time = bsb.to_datetime(end_time)
        
            is_demo = bsb.to_bool(self.request.get("is_demo"))

            if (not start_time) or (not end_time):
                state.addError("You must specify a start time and an end time for your booking!")
                return self._itemCalendarPage(state, item, acl, is_demo=is_demo)

            try:
                reservation = item.makeReservation(state.account, acl, start_time, end_time, is_demo=is_demo)
            except bsb.equipment.BookingError as e:
                state.addError(e.errorMessage())
                return self._itemCalendarPage(state, item, acl, is_demo=is_demo)

            if not is_demo:
                state.setTemplate("equipment", item)
                state.setTemplate("reservation", reservation)
                state.setTemplate("requirements", item.getRequirements())
                self.write(state, "confirm_reservation.html", "Equipment | Confirm Reservation")
            else:
                state.setTemplate("page_title", "Demo booking successful")
                (start_time,end_time) = item.constraints.validate(start_time,end_time)
                state.setTemplate("page_content", 
                                  ["Demo booking entered betweeen %s and %s." % (start_time,end_time),
                                   "<a href=\"/equipment/item/%s/admin_cons\">Return to editing page...</a>" % item.idstring])
                self.write(state, "simple_content.html", "Equipment | Booking (DEMO)")

            return

        elif action == "resume_booking":
            reservation = bsb.equipment.BookingInfo( equipment=item.idstring,
                                                     booking_id=bsb.to_string(self.request.get("reservation",None)) )
            state.setTemplate("equipment", item)
            state.setTemplate("reservation", reservation)
            state.setTemplate("requirements", item.getRequirements())
            self.write(state, "confirm_reservation.html", "Equipment | Confirm Reservation")
            return

        elif action == "demo_booking":
            state.setTemplate("equipment", item)
            state.setTemplate("reservation", None)
            state.setTemplate("requirements", item.getRequirements())
            self.write(state, "confirm_reservation.html", "Equipment | Demo Booking")
            return

        elif action in ["demo_confirm","confirm_booking"]:
            is_demo = (action == "demo_confirm")

            if not is_demo:
                reservation = bsb.equipment.BookingInfo( equipment=item.idstring,
                                                         booking_id=bsb.to_string(self.request.get("reservation",None)) )
                state.setTemplate("reservation", reservation)

            if not is_post:
                raise ProgramBug( "You can only confirm bookings using HTTP post" )

            # get the name of the project
            project = bsb.to_string(self.request.get("project"))

            errors = []

            if not project:
                errors.append( "You must specify the project to which this booking will be assigned." )

            requirements = item.getRequirements()

            if requirements:
                try:
                    user_reqs = requirements.processResponse(self.request, is_demo=is_demo)
                except Exception as e:
                    for d in e.detail:
                        errors.append( d.message )
            else:
                user_reqs = None

            if len(errors) > 0:
                state.addErrors(errors)
                state.setTemplate("project", project)

                supplied = {}
                for requirement in requirements.requirements:
                    value = bsb.to_string(self.request.get(requirement.reqid,None))
                    if value:
                        supplied[requirement.reqid] = value

                state.setTemplate("supplied", supplied)
                state.setTemplate("equipment", item)
                state.setTemplate("requirements", item.getRequirements())
                state.setTemplate("booking_action", action)
                self.write(state, "confirm_reservation.html", "Equipment | Demo Booking")
                return

            if is_demo:
                state.setTemplate("page_title", "Demo booking successful!")

                content = ["The demo booking has been successful!"]

                requirements = user_reqs.equipmentRequirements()

                for i in range(0, len(requirements.requirements)):
                    req = requirements.requirements[i]
                    user = user_reqs.requirements[i]

                    if req.reqname != user.reqname:
                        raise ProgramBug("Problem with matching user input to requirement", detail=[req,user])

                    content.append( "Value of '%s' equals '%s'" % (req.reqname, user.reqvalue))
           
                content.append("<a href='/equipment/item/%s/admin_reqs'>Click here</a> to return to the booking customisation page.</a>" % item.idstring)

                state.setTemplate("page_content", content)

                self.write(state, "simple_content.html", "Equipment | Demo Booking")
                return

            else:
                if not reservation.booking_id:
                    state.addError("Cannot find the reservation with booking ID = %s" % bsb.to_string(self.request.get("reservation",None)))
                else:
                    try:
                        booking = item.confirmBooking(state.account, acl, reservation.booking_id, project, user_reqs)
                        self.redirect("/equipment/item/%s/view_booking?reservation=%s" % \
                                      (item.idstring,booking.booking_id))
                    except bsb.equipment.BookingError as e:
                        state.addError(e.errorMessage())

        elif action == "demo_reserving":
            state.setTemplate("is_demo", True)

        else:
            state.addError("Unrecognised action '%s'" % action)

        self._itemCalendarPage(state, item, acl)

    def itemAdminConsPage(self, state, item, acl, is_post):
        if not acl.isAdministrator(): 
            state.addError("You do not have permission to administer this piece of equipment")
            return self.itemPage(state, item.idstring, is_post)

        state.setTemplate("enable_popovers", True)
        state.setTemplate("bookable_units", bsb.equipment.BookingConstraint.bookableUnitTypes())

        cons = item.getConstraints(create_if_nonexistant=True)

        if len(state.extra_paths) > 3:
            action = state.extra_paths[3]

            if action == "edit_info":
                if is_post:
                    info = bsb.to_string(self.request.get("information", None))
                    cons.setInformation(state.account, acl, item, info)
                    self.redirect("/equipment/item/%s/admin_cons" % item.idstring)
                else:
                    state.setTemplate("edit_info", True)

            elif action == "edit_unit":
                if is_post:
                    unit = bsb.to_string(self.request.get("unit", None))

                    if unit:
                        cons.setBookableUnit(state.account, acl, item, unit)

                    self.redirect("/equipment/item/%s/admin_cons" % item.idstring)
                else:
                    state.setTemplate("edit_unit", True)

            elif action == "edit_days":
                if is_post:
                    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

                    ok_days = []

                    for day in days:
                        ok_days.append( bsb.to_bool(self.request.get(day,None)) )

                    cons.setBookableDays(state.account, acl, item, ok_days)
                    self.redirect("/equipment/item/%s/admin_cons" % item.idstring)
                else:
                    state.setTemplate("edit_days", True)

            elif action == "edit_mintime":
                if is_post:
                    mintime = bsb.fromDaysHoursMinutes(self.request.get("mintime",None), "none")
                    cons.setMinimumTime(state.account, acl, item, mintime)
                    self.redirect("/equipment/item/%s/admin_cons" % item.idstring)
                else:
                    state.setTemplate("edit_mintime", True)

            elif action == "edit_maxtime":
                if is_post:
                    maxtime = bsb.fromDaysHoursMinutes(self.request.get("maxtime",None), "forever")
                    cons.setMaximumTime(state.account, acl, item, maxtime)
                    self.redirect("/equipment/item/%s/admin_cons" % item.idstring)
                else:
                    state.setTemplate("edit_maxtime", True)

            elif action == "edit_range":
                if is_post:
                    range_start = bsb.to_string(self.request.get("range_start",None))
                    range_end = bsb.to_string(self.request.get("range_end",None))

                    if range_start and range_end:
                        cons.setBookingRange(state.account, acl, item, range_start, range_end)
                    else:
                        cons.removeBookingRange(state.account, acl, item)

                    self.redirect("/equipment/item/%s/admin_cons" % item.idstring)
                else:
                    state.setTemplate("edit_range", True)

            else:
                state.addError("Unrecognised action '%s'" % action)

        state.setTemplate("constraints", cons)
        self.write(state, "administer_constraints.html", "Equipment | %s" % item.name)

    def itemAdminReqsPage(self, state, item, acl, is_post):
        if not acl.isAdministrator(): 
            state.addError("You do not have permission to administer this piece of equipment")
            return self.itemPage(state, item.idstring, is_post)

        requirements = item.getRequirements(True)
        state.setTemplate("requirements", requirements)
        state.setTemplate("requirement_types", bsb.equipment.RequirementTypes())

        view_req = bsb.to_string(self.request.get("view_req",None))
        if view_req:
            state.setTemplate("view_req", view_req)

        if len(state.extra_paths) > 3:
            action = state.extra_paths[3]

            if action == "edit_intro":
                if is_post:
                    intro = bsb.to_string(self.request.get("introduction", None))
                    requirements.setIntroduction(state.account, acl, intro)
                    self.redirect("/equipment/item/%s/admin_reqs" % item.idstring)
                else:
                    state.setTemplate("edit_intro", True)

            elif action == "edit_auth":
                if is_post:
                    needs_authorisation = bsb.to_bool(self.request.get("needs_authorisation", None))
                    requirements.setNeedsAuthorisation(state.account, acl, needs_authorisation)
                    self.redirect("/equipment/item/%s/admin_reqs" % item.idstring)
                else:
                    state.setTemplate("edit_auth", True)

            elif action == "edit_req":
                if is_post:
                    name = bsb.to_string(self.request.get("req_name",None))
                    help = bsb.to_string(self.request.get("req_help",None))
                    reqtype = bsb.to_string(self.request.get("req_type",None))
                    allowed_values = bsb.to_string(self.request.get("allowed_values",None))
                    requirements.setRequirement(state.account, acl, name, reqtype, allowed_values, help)
                    self.redirect("/equipment/item/%s/admin_reqs?view_req=%s" % (item.idstring,name))
                else:
                    name = bsb.to_string(self.request.get("req_name",None))
                    state.setTemplate("edit_req", name)

            elif action == "add_req":
                if is_post:
                    name = bsb.to_string(self.request.get("req_name",None))
                    help = bsb.to_string(self.request.get("req_help",None))
                    allowed_values = bsb.to_string(self.request.get("allowed_values",None))
                    reqtype = bsb.to_string(self.request.get("req_type",None))
                    requirements.setRequirement(state.account, acl, name, reqtype, allowed_values, help)
                    self.redirect("/equipment/item/%s/admin_reqs" % item.idstring)

            elif action == "move_up":
                name = bsb.to_string(self.request.get("req_name",None))
                requirements.moveUp(state.account, acl, name)
                self.redirect("/equipment/item/%s/admin_reqs" % item.idstring)

            elif action == "move_down":
                name = bsb.to_string(self.request.get("req_name",None))
                requirements.moveDown(state.account, acl, name)
                self.redirect("/equipment/item/%s/admin_reqs" % item.idstring)

            elif action == "del_req":
                name = bsb.to_string(self.request.get("req_name",None))
                state.setTemplate("really_delete", name)

            elif action == "really_del_req":
                name = bsb.to_string(self.request.get("req_name",None))
                requirements.deleteRequirement(state.account, acl, name)
                self.redirect("/equipment/item/%s/admin_reqs" % item.idstring)

            else:
                raise bsb.InputError("Unrecognised action '%s' for post state '%s'" % (action,is_post))

        self.write(state, "administer_equipreq.html", "Equipment | %s" % item.name)

    def itemAdminPage(self, state, item, acl, is_post):
        if not acl.isAdministrator():
            state.addError("You do not have permission to administer this piece of equipment")
            return self.itemPage(state, item.idstring, is_post)

        hide_actions = bsb.to_bool( self.request.get("hide_actions",None) )
        show_bookings = bsb.to_bool( self.request.get("show_bookings",None) )
        show_users = bsb.to_bool( self.request.get("show_users",None) )
        show_admin = bsb.to_bool( self.request.get("show_admin",None) )

        view_options = "show_admin=%s&hide_actions=%s&show_bookings=%s&show_users=%s" % \
                            (show_admin,hide_actions,show_bookings,show_users)
        admin_url = "/equipment/item/%s/admin?%s" % (item.idstring,view_options)

        state.setTemplate("show_actions", not hide_actions)
        state.setTemplate("show_admin", show_admin)
        state.setTemplate("show_bookings", show_bookings)
        state.setTemplate("show_users", show_users)
        state.setTemplate("view_options", view_options)

        base_url = "/equipment/item/%s/admin" % item.idstring
        state.setTemplate("show_admin_url", "%s?show_admin=True&hide_actions=%s&show_bookings=%s&show_users=%s" % (base_url,hide_actions,show_bookings,show_users))
        state.setTemplate("hide_admin_url", "%s?show_admin=False&hide_actions=%s&show_bookings=%s&show_users=%s" % (base_url,hide_actions,show_bookings,show_users))
        state.setTemplate("show_actions_url", "%s?show_admin=%s&hide_actions=False&show_bookings=%s&show_users=%s" % (base_url,show_admin,show_bookings,show_users))
        state.setTemplate("hide_actions_url", "%s?show_admin=%s&hide_actions=True&show_bookings=%s&show_users=%s" % (base_url,show_admin,show_bookings,show_users))
        state.setTemplate("show_bookings_url", "%s?show_admin=%s&hide_actions=%s&show_bookings=True&show_users=%s" % (base_url,show_admin,hide_actions,show_users))
        state.setTemplate("hide_bookings_url", "%s?show_admin=%s&hide_actions=%s&show_bookings=False&show_users=%s" % (base_url,show_admin,hide_actions,show_users))
        state.setTemplate("show_users_url", "%s?show_admin=%s&hide_actions=%s&show_bookings=%s&show_users=True" % (base_url,show_admin,hide_actions,show_bookings))
        state.setTemplate("hide_users_url", "%s?show_admin=%s&hide_actions=%s&show_bookings=%s&show_users=False" % (base_url,show_admin,hide_actions,show_bookings))

        if len(state.extra_paths) > 3:
            action = state.extra_paths[3]

            if action == "grant_access" and is_post:
                pending_user = self.request.get("pending_user", None)
                pending_user = bsb.to_email(pending_user)
                if pending_user:
                    item.setUserIsAuthorised(state.account, pending_user, None)
                self.redirect(admin_url)
            elif action == "ban_user" and is_post:
                banned_user = self.request.get("banned_user", None)
                reason = self.request.get("reason", None)
                banned_user = bsb.to_email(banned_user)
                reason = bsb.to_string(reason)

                if reason:
                    if banned_user:
                        item.setUserIsBanned(state.account, banned_user, reason)

                    self.redirect(admin_url)
                else:
                    state.addError("You cannot deny access to someone without giving them a reason")
            elif action == "unban_user" and is_post:
                unbanned_user = self.request.get("unbanned_user", None)
                unbanned_user = bsb.to_email(unbanned_user)
                if unbanned_user:
                    item.setUserIsAuthorised(state.account, unbanned_user, None)
                self.redirect(admin_url)
            elif action == "grant_admin" and is_post:
                admin_user = self.request.get("admin_user", None)
                admin_user = bsb.to_email(admin_user)
                if admin_user:
                    item.setUserIsAdministrator(state.account, admin_user, None)
                self.redirect(admin_url)
            elif action == "revoke_admin" and is_post:
                admin_user = self.request.get("admin_user", None)
                reason = self.request.get("reason", None)
                admin_user = bsb.to_email(admin_user)
                reason = bsb.to_string(reason)

                if reason:
                    if admin_user:
                        item.setUserIsAuthorised(state.account, admin_user, reason)
                    self.redirect(admin_url)
                else:
                    state.addError("You cannot revoke admin rights without providing a reason")
            elif action == "allow_booking" and is_post:
                booking_id = bsb.to_string(self.request.get("booking_id",None))
                if booking_id:
                    item.allowBooking(state.account, acl, booking_id)
            	self.redirect(admin_url)
            elif action == "deny_booking" and is_post:
                reason = bsb.to_string(self.request.get("reason",None))
                booking_id = bsb.to_string(self.request.get("booking_id",None))

                if reason:
                    if booking_id:
                        item.denyBooking(state.account, acl, booking_id, reason)
                    self.redirect(admin_url)
                else:
                    state.addError("You cannot deny a booking without providing a reason")
            elif action == "cancel_booking" and is_post:
                reason = bsb.to_string(self.request.get("reason",None))
                booking_id = bsb.to_string(self.request.get("booking_id",None))

                if reason:
                    if booking_id:
                        item.denyBooking(state.account, acl, booking_id, "CANCELLED BY ADMIN: %s" % reason)
                    self.redirect(admin_url)
                else:
                    state.addError("You cannot cancel a booking without providing a reason")
            else:
                state.addError("Unrecognised action '%s' for post state '%s'" % (action,is_post))

        if not hide_actions:
            state.setTemplate("pending_users", item.getPendingUsers(state.account,include_reasons=True))
            state.setTemplate("pending_bookings", item.getPendingBookings(state.account,acl))
            state.setTemplate("calendar", item.getCalendar(state.account))

        if show_users:
            state.setTemplate("banned_users", item.getBannedUsers(state.account,include_reasons=True))
            state.setTemplate("authorised_users", item.getAuthorisedUsers(state.account))
            state.setTemplate("admin_users", item.getAdministratorUsers(state.account))

        if show_bookings:
            now_time = bsb.get_now_time()
            today_start = bsb.get_day_from(now_time)
            tomorrow_start = today_start + datetime.timedelta(days=1)

            state.setTemplate("todays_bookings", item.getBookings(state.account, acl,
                                                                  start_time=now_time, end_time=tomorrow_start,
                                                                  status=bsb.equipment.Booking.confirmed()))

            state.setTemplate("future_bookings", item.getBookings(state.account, acl,
                                                                  start_time=tomorrow_start,
                                                                  status=bsb.equipment.Booking.confirmed()))

        state.setTemplate("account_mapping", bsb.accounts.get_account_mapping())

        self.write(state, "administer_equipment.html", "Equipment | %s" % item.name)

    def viewBookingPage(self, state, item, acl, is_post):
        """Page used to view the details of an individual booking"""
        booking_id = bsb.to_string(self.request.get("reservation",None))

        if not booking_id:
            raise bsb.InputError("You need to specify the booking ID number of the booking you want to view!")

        reservation = bsb.equipment.BookingInfo(equipment=item.idstring, booking_id=booking_id)
        state.setTemplate("booking", reservation)
        state.setTemplate("really_cancel", bsb.to_string(self.request.get("really_cancel",None)))
        state.setTemplate("is_admin_view", bsb.to_bool(self.request.get("is_admin_view",None)))

        requirements = reservation.getRequirements()

        if requirements:
            state.setTemplate("requirements", requirements.equipmentRequirements())
            state.setTemplate("user_values", requirements)

        self.write(state, "view_reservation.html", "Equipment | View Booking")

    def itemPage(self, state, item_id, is_post):
        item_id = bsb.to_string(item_id)

        if not item_id:
            return self.redirect("/equipment/summary")

        item = bsb.equipment.get_equipment(item_id)

        if not item:
            state.setTemplate("Cannot find the piece of equipment with ID '%s'" % item_id)
            return self.overviewPage(state, is_post)

        acl = item.getACL(state.account)
        
        # we don't want to see the second set of menu links
        state.setTemplate("second_menu_links", None)

        state.setTemplate("item", item)
        state.setTemplate("acl", acl)
        state.setTemplate("laboratory_mapping", bsb.equipment.get_laboratory_mapping())
        state.setTemplate("type_mapping", bsb.equipment.get_equipment_type_mapping())
        state.setTemplate("projects", bsb.projects.get_sorted_project_mapping())
        state.setTemplate("project_mapping", bsb.projects.get_project_mapping())

        # get the list of any current, unresolved reported problems with this piece of equipment,
        # so at least the user can see if something is wrong when they are making the booking
        unresolved_problems = item.getUnresolvedFeedBack()

        if unresolved_problems:
            state.addError("<strong>There are currently unresolved problems with this piece of equipment.</strong>")
            i = 0
            for problem in unresolved_problems:
                i += 1
                state.addError("<a href=\"/feedback/view/%s\">Problem %d: %s</a>"  % \
                                 (problem.feedback_id, i, problem.description()))

            state.addError("For more information, click on the above problem(s). Please bear this in mind if you are planning on using this equipment today.")
 
        if len(state.extra_paths) > 2:
            action = state.extra_paths[2]

            if action == "book":
                if acl and acl.isAuthorised():
                    return self.itemBookingPage(state, item, acl, is_post)
                else:
                    state.addError("You do not have permission to book this piece of equipment")

            elif action == "view_booking":
                if acl and acl.isAuthorised():
                    return self.viewBookingPage(state, item, acl, is_post)
                else:
                    state.addError("You do not have permission to view bookings for this piece of equipment")

            elif action == "cancel":
                if acl and acl.isAuthorised():
                    reservation = self.request.get("reservation")
                    try:
                        message = item.cancelBooking(state.account, acl, reservation)
                        state.addMessage(message)
                    except bsb.equipment.BookingError as e:
                        state.addError(e.errorMessage())
 
            elif action == "admin":
                if acl and acl.isAdministrator():
                    return self.itemAdminPage(state, item, acl, is_post)
                else:
                    state.addError("You do not have permission to administer this piece of equipment")

            elif action == "admin_reqs":
                if acl and acl.isAdministrator():
                    return self.itemAdminReqsPage(state, item, acl, is_post)
                else:
                    state.addError("You do not have permission to administer user requirements for this piece of equipment")

            elif action == "admin_cons":
                if acl and acl.isAdministrator():
                    return self.itemAdminConsPage(state, item, acl, is_post)
                else:
                    state.addError("You do not have permission to administer booking constraints for this piece of equipment")

            elif action == "request_access" and is_post:
                pending_user = self.request.get("pending_user", None)
                reason = self.request.get("reason", None)
                pending_user = bsb.to_email(pending_user)
                reason = bsb.to_string(reason)
                if not reason:
                    state.addError("You must tell us why you want access to this piece of equipment.")
                else:
                    item.setUserIsPending(state.account, pending_user, reason)
                    self.redirect("/equipment/item/%s" % item.idstring)

            else:
                state.addError("Unknown action '%s' for this piece of equipment." % action)

        self._itemCalendarPage(state, item, acl)

    def mapPage(self, state, is_post):
        state.setTemplate("map_html", """<iframe width="100%" height="600" frameborder="0" scrolling="no" marginheight="0" marginwidth="0" src="https://maps.google.com/maps?f=q&amp;source=s_q&amp;hl=en&amp;geocode=&amp;q=university+of+bristol&amp;aq=&amp;sll=37.0625,-95.677068&amp;sspn=56.856075,135.263672&amp;ie=UTF8&amp;hq=&amp;hnear=&amp;t=m&amp;iwloc=A&amp;ll=51.458417,-2.602979&amp;spn=0.006295,0.006295&amp;output=embed"></iframe><br /><small><a href="https://maps.google.com/maps?f=q&amp;source=embed&amp;hl=en&amp;geocode=&amp;q=university+of+bristol&amp;aq=&amp;sll=37.0625,-95.677068&amp;sspn=56.856075,135.263672&amp;ie=UTF8&amp;hq=&amp;hnear=&amp;t=m&amp;iwloc=A&amp;ll=51.458417,-2.602979&amp;spn=0.006295,0.006295" style="color:#0000FF;text-align:left">View Larger Map</a></small>""")
        self.write(state, "map.html", "Equipment | Map")

    def bookingsPage(self, state, is_post):
        if len(state.extra_paths) > 1:
            action = state.extra_paths[1]

            if action == "cancel":
                equipment = self.request.get("equipment", None)
                reservation = self.request.get("reservation", None)

                item = bsb.equipment.get_equipment(equipment)

                if item:
                    acl = item.getACL(state.account)
                    item.cancelBooking(state.account, acl, reservation)
                    return self.redirect("/equipment/bookings")
            else:
                state.addError("Unrecognised action '%s'" % action)

        state.setTemplate("equipment_mapping", bsb.equipment.get_equipment_mapping())
        state.setTemplate("laboratory_for_equipment", bsb.equipment.get_laboratory_for_equipment_mapping())
        state.setTemplate("type_for_equipment", bsb.equipment.get_type_for_equipment_mapping())
        now_time = bsb.get_now_time()
        today_start = bsb.get_day_from(now_time)
        tomorrow_start = today_start + datetime.timedelta(days=1)
        state.setTemplate("today_bookings", bsb.equipment.get_bookings_for_user(state.account,
                                                range_start=today_start, range_end=tomorrow_start))
        state.setTemplate("bookings", bsb.equipment.get_bookings_for_user(state.account, range_start=tomorrow_start))

        old_range_start = bsb.to_date(self.request.get("range_start"))
        old_range_end = bsb.to_date(self.request.get("range_end"))

        if old_range_start and old_range_end:
            if old_range_start > old_range_end:
                tmp = old_range_start
                old_range_start = old_range_end
                old_range_end = tmp

            if old_range_start > today_start:
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
        state.setTemplate("newer_range_end", min(now_time, old_range_end + datetime.timedelta(days=7)))

        state.setTemplate("old_bookings", bsb.equipment.get_bookings_for_user(state.account, range_start=old_range_start,
                                                                              range_end=old_range_end, reverse_sort=True))

        state.setTemplate("really_cancel", self.request.get("really_cancel"))

        self.write(state, "bookings.html", "Equipment | Bookings")

    def render_get(self, state):
        self.render_post(state, False)

    def render_post(self, state, is_post=True):
        state.addParentPage("/equipment")

        if state.extra_paths and state.extra_paths[0] in ["summary", "map", "labs", "types", "item", "bookings"]:
            state.addParentPage("/equipment/%s" % state.extra_paths[0])
        else:
            state.addParentPage("/equipment/summary")

        #state = self.buildSubMenu(state, main_menu_items)        

        state.setTemplate("account_mapping", bsb.accounts.get_account_mapping())

        if state.extra_paths:
            if state.extra_paths[0] == "labs":
                if len(state.extra_paths) > 1:
                    return self.labsPage(state, state.extra_paths[1], is_post)
                else:
                    return self.browsePage(state, False, is_post)
            elif state.extra_paths[0] == "types":
                if len(state.extra_paths) > 1:
                    return self.typesPage(state, state.extra_paths[1], is_post)
                else:
                    return self.browsePage(state, True, is_post)
            elif state.extra_paths[0] == "map":
                return self.mapPage(state, is_post)
            elif state.extra_paths[0] == "bookings":
                return self.bookingsPage(state, is_post)
            elif state.extra_paths[0] == "item":
                return self.itemPage(state, state.extra_paths[1], is_post)
            elif state.extra_paths[0] != "summary":
                state.addError("Unrecognised action '%s'" % state.extra_paths[0])

        self.overviewPage(state, is_post)
