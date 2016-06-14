# -*- coding: utf-8 -*-
"""All of the pages used by the application to manage and schedule equipment"""

# base pages
import base_pages

# datetime interface
import datetime

# BSB interface
import bsb

class ReportBugPage(base_pages.BasePostPage):

    def render_get(self, state):
        return

    def render_post(self, state):
        bug_id = bsb.to_int( self.request.get("bug_id", None) )

        if not bug_id:
            raise bsb.DataError("You must supply the bug_id of the bug to which you wish to add data")

        user_info = bsb.to_string(self.request.get("user_info", None))

        if not user_info:
            self.response.write("Nothing added")
            return

        bug = bsb.feedback.BugInfo(bug_id=bug_id)
        bug.setUserInfo(state.account, user_info)

        state.setTemplate("page_title", "Thanks")
        state.setTemplate("page_content", ["Thank you for submitting extra information about this bug.",
                                           """This will really help the administrators understand why this error occurred
                                              and will give them the knowledge needed to quickly fix it."""])

        self.write(state, "simple_content.html", "Thanks")
 
class ReportProblemPage(base_pages.BasePostPage):

    def render_get(self, state):
        self.render_post(state, False)

    def printOverview(self, state):
        state.setTemplate("page_title", "Report a Problem")
        state.setTemplate("page_content", 
                            ["""<ul><li><a href="/forum/create?topic_type=equipment_problem">equipment problem</a></li>
                                    <li><a href="/forum/create?topic_type=booking_problem">booking problem</a></li>
                                    <li><a href="/forum/create?topic_type=website_problem">website problem</a></li></ul>"""])

        self.write(state, "simple_content.html", "Report a problem")

    def report_equipment_problem(self, state, idstring, is_post):
        equipment = bsb.equipment.get_equipment(idstring)

        if not equipment:
            state.addError("Unrecognised piece of equipment '%s'" % idstring)
            self.printOverview(state)
            return

        if is_post:
            problem_type = bsb.to_string(self.request.get("problem_type", None))
            problem_description = bsb.to_string(self.request.get("problem_description", None))

            if problem_type and problem_description:
                feedback = bsb.feedback.FeedBackInfo.createFromEquipmentProblem(state.account, equipment, 
                                                                                problem_type, problem_description)

                state.setTemplate("page_title", "Thanks")
                state.setTemplate("page_content", ["Thanks for telling us about the problem.",
                      "The administrators and the equipment owners have been notified.",
                      "Hopefully they should be able to resolve this problem soon."])
                self.write(state, "simple_content.html", "Thanks")
                return
            else:
                if not problem_type:
                    state.addError("Please select the type of problem.")

                if not problem_description:
                    state.addError("Please provide a description of the problem.")

                state.setTemplate("chosen_problem", problem_type)
                state.setTemplate("chosen_description", problem_description)
                     
        state.setTemplate("item", equipment)
        state.setTemplate("laboratory_mapping", bsb.equipment.get_laboratory_mapping())
        state.setTemplate("type_mapping", bsb.equipment.get_equipment_type_mapping())
        state.setTemplate("problem_types", bsb.feedback.FeedBackInfo.equipmentProblemTypes())
        self.write(state, "report_equipment_problem.html", "Report Problem With %s" % equipment.name)

    def render_post(self, state, is_post=True):

        equipment = bsb.to_string(self.request.get("equipment",None))

        if equipment:
            return self.report_equipment_problem(state, equipment, is_post)

        self.printOverview(state)

class ViewForumPage(base_pages.BasePostPage):

    def render_get(self, state):
        self.render_post(state, False)

    def overviewPage(self, state, is_post):
        now_time = bsb.get_now_time()
        today_start = bsb.get_day_from(now_time)

        topic_mask = bsb.to_string(self.request.get("topic_mask"))

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

        state.setTemplate("topic_mask", topic_mask)

        state.setTemplate("feedback_types", bsb.feedback.FeedBackInfo.feedbackTypes())

        state.setTemplate("today_start", today_start)

        state.setTemplate("range_start", old_range_start)
        state.setTemplate("range_end", old_range_end)

        state.setTemplate("older_range_start", old_range_start - datetime.timedelta(days=7))
        state.setTemplate("older_range_end", old_range_start)

        state.setTemplate("newer_range_start", old_range_end)
        state.setTemplate("newer_range_end", min(today_start, old_range_end + datetime.timedelta(days=7)))

        if topic_mask is None:
            topic_mask = "open"

        state.setTemplate("feedback", bsb.feedback.get_feedback(state.account, old_range_start, 
                                                                old_range_end + datetime.timedelta(days=1),
                                                                topic_mask=topic_mask))

        self.write(state, "view_forum.html", "Forum")

    def createNewTopic(self, state, topic_title, topic_type):
        if not topic_type:
            return

        topic_description = bsb.feedback.FeedBack.stringToDescription(topic_type)
        message = bsb.to_string(self.request.get("message",None))
        topic_title = bsb.to_string(self.request.get("topic_title",None))

        state.setTemplate("topic_title", topic_title)
        state.setTemplate("topic_type", topic_type)
        state.setTemplate("topic_description", topic_description)

        if message:
            state.setTemplate("message", message)

        if topic_type == "equipment_problem":
            state.setTemplate("equipment_topic", True)
            state.setTemplate("problem_types", bsb.feedback.FeedBackInfo.equipmentProblemTypes())
            state.setTemplate("equipment_hierarchy", bsb.equipment.get_equipment_hierarchy())

        elif topic_type == "booking_problem":
            state.setTemplate("equipment_topic", True)
            state.setTemplate("booking_topic", True)
            state.setTemplate("equipment_hierarchy", bsb.equipment.get_equipment_hierarchy())

        elif state.extra_paths and state.extra_paths[0] == "create_topic":
            if message and topic_title:
                feedback = bsb.feedback.FeedBackInfo.createFrom(state.account, topic_title, topic_type, message=message)
                self.redirect("/forum")
                return
            else:
                state.addError("You must supply a title and an initial starting message")

        self.write(state, "create_topic.html", "Forum | Create New...")

    def render_post(self, state, is_post=True):
        state.setTemplate("account_mapping", bsb.accounts.get_account_mapping())

        if is_post:
            topic_type = bsb.to_string( self.request.get("topic_type",None) )

            if topic_type:
                return self.createNewTopic(state, None, topic_type)

        elif state.extra_paths and state.extra_paths[0] == "create":
            topic_type = bsb.to_string( self.request.get("topic_type",None) )

            if topic_type:
                return self.createNewTopic(state, None, topic_type)
            

        self.overviewPage(state, is_post)


class ViewFeedBackPage(base_pages.BasePostPage):

    def render_get(self, state):
        self.render_post(state, False)

    def render_post(self, state, is_post=True):
        feedback_id = int(state.extra_paths[0])

        feedback = bsb.feedback.FeedBackInfo(feedback_id=feedback_id)

        if not feedback:
            raise bsb.InvalidIDError("No feedback with ID = '%s'" % feedback_id)

        resolve_info = bsb.to_string(self.request.get("resolved_info",None))
        is_resolved = bsb.to_bool(self.request.get("is_resolved",None))

        if is_post:
            if is_resolved:
                feedback.markAsResolved(state.account, resolve_info)
                resolve_info = None

            else:
                feedback.addExtraInformation(state.account, resolve_info)
                resolve_info = None

            self.redirect(self.request.uri)

        state.setTemplate("feedback", feedback)
        state.setTemplate("resolved_info", resolve_info)
        state.setTemplate("account_mapping", bsb.accounts.get_account_mapping())

        self.write(state, "view_feedback.html", "FeedBack")


class LeaveFeedBackPage(base_pages.BasePostPage):

    def render_get(self, state):
        self.render_post(state, False)

    def render_post(self, state, is_post=True):
        self.redirect("/forum/create?topic_type=website_feedback")
