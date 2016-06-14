# -*- coding: utf-8 -*-
"""All of the pages used by the application to get reports"""

# base pages
import base_pages

# BSB interface
import bsb

class ReportPage(base_pages.BasePostPage):
    """Class that handles the main report page"""

    def _printPage(self, state):
        self.write(state, "report.html", "Reports")

    def render_get(self, state):
        self._printPage(state)

    def render_post(self, state):
        self._printPage(state)
