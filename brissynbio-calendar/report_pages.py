# -*- coding: utf-8 -*-

import webapp2

# base pages
import base_pages

# dates and times
import datetime

# BSB interface
import bsb

from oauth2client import client

class ReportPage(base_pages.BaseGetPage):
    """Class that allows you to generate reports of usage"""

    def needsAdmin(self):
        return False

    def render_get(self, state):
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

        state.setTemplate("account_mapping", bsb.accounts.get_account_mapping())

        bookings = bsb.equipment.get_bookings(start_time=old_range_start, end_time=old_range_end)

        equip_stats = {}
        proj_stats = {}
        user_stats = {}

        total_time = 0
        nbookings = 0

        for booking in bookings:
            if not booking.isConfirmed():
                continue

            run_time = (booking.end_time - booking.start_time).total_seconds() / 60.0
            total_time += run_time
            equip = booking.equipment
            proj = booking.project
            email = booking.email
            nbookings += 1

            if proj is None:
                state.addError( "No project for booking %s %s" % (equip,email) )

            if not equip in equip_stats:
                equip_stats[equip] = {}
                equip_stats[equip]["_total"] = 0

            if not proj in proj_stats:
                proj_stats[proj] = {}
                proj_stats[proj]["_total"] = 0

            if not email in user_stats:
                user_stats[email] = {}
                user_stats[email]["_total"] = 0

            if not proj in equip_stats[equip]:
                equip_stats[equip][proj] = 0.0

            if not email in equip_stats[equip]:
                equip_stats[equip][email] = 0.0

            if not proj in user_stats[email]:
                user_stats[email][proj] = 0.0

            if not equip in user_stats[email]:
                user_stats[email][equip] = 0.0

            if not equip in proj_stats[proj]:
                proj_stats[proj][equip] = 0.0

            if not email in proj_stats[proj]:
                proj_stats[proj][email] = 0.0

            equip_stats[equip]["_total"] += run_time
            equip_stats[equip][proj] += run_time
            equip_stats[equip][email] += run_time
            proj_stats[proj]["_total"] += run_time
            proj_stats[proj][equip] += run_time
            proj_stats[proj][email] += run_time
            user_stats[email]["_total"] += run_time
            user_stats[email][proj] += run_time
            user_stats[email][equip] += run_time

        equips = list(equip_stats.keys())
        equips.sort()
        projs = list(proj_stats.keys())
        projs.sort()
        emails = list(user_stats.keys())
        emails.sort()

        state.setTemplate("equips_dict", bsb.equipment.get_equipment_dict())
        state.setTemplate("projects_dict", bsb.projects.get_project_mapping())
        state.setTemplate("emails_dict", bsb.accounts.get_account_mapping())

        state.setTemplate("nbookings", nbookings)
        state.setTemplate("nemails", len(emails))
        state.setTemplate("nprojs", len(projs))
        state.setTemplate("nequips", len(equips))
        state.setTemplate("total_time", total_time)

        state.setTemplate("equips", equips)
        state.setTemplate("projs", projs)
        state.setTemplate("emails", emails)
        state.setTemplate("equip_stats", equip_stats)
        state.setTemplate("proj_stats", proj_stats)
        state.setTemplate("email_stats", user_stats)

        self.write(state, "report.html", "Booking Reports")
