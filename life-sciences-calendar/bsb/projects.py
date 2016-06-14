# -*- coding: utf-8 -*-

"""Module containing all classes needed to describe and manage the 
   projects used by the BrisSynBio equipment scheduler"""

from google.appengine.ext import ndb

# regular expression module used to validate project details
import re

from bsb import *

# uses the db module, which should be kept private
import bsb._db as _db

# The default registry of projects
DEFAULT_PROJECT_REGISTRY = "bsb.equipment.projects"

def project_key(project_registry=DEFAULT_PROJECT_REGISTRY):
    """Constructs a Datastore key for a project entry.
       We use the project name as the key"""
    return ndb.Key('Accounts', project_registry)

class Project(ndb.Model):
    #human readable name of the project
    name = ndb.StringProperty(indexed=False)

    #Whether or not this is a core BrisSynBio project
    bsb_project = ndb.BooleanProperty(indexed=False)

    #Whether or not this project is VAT exempt
    vat_exempt = ndb.BooleanProperty(indexed=False)

    # Human readable information about the user
    information = ndb.JsonProperty(indexed=False)

    def setFromInfo(self, info):
        _db.setFromInfo(self, info)
        self.bsb_project = info.bsb_project
        self.vat_exempt = info.vat_exempt

    @classmethod
    def getQuery(cls, registry=DEFAULT_PROJECT_REGISTRY):
        return cls.query(ancestor=project_key(registry))

    @classmethod
    def ancestor(cls, registry=DEFAULT_PROJECT_REGISTRY):
        return project_key(registry)

class ProjectInfo(_db.StandardInfo):
    """Simple class that holds the non-sensitive information about a project"""
    def __init__(self, project=None, registry=DEFAULT_PROJECT_REGISTRY):
        _db.StandardInfo.__init__(self, project, registry)

        if project:
            self.title = project.name
            self.bsb_project = project.bsb_project
            self.vat_exempt = project.vat_exempt
            self.name = project.name    

    @classmethod
    def getAll(cls, account, registry=None):
        """Return all of the items in the database"""
        return _db.getAllFromDB(account, Project, registry)

    @classmethod
    def backup(cls, account, registry=None):
        """Return a string containing the entire database in pickled form"""
        return _db.backup(account, cls, Project, registry)

    @classmethod
    def restore(cls, account, data, registry=None):
        """Restore the database from the passed 'data' string containing a pickle of all of the objects"""
        _db.restore(account, cls, Project, data, registry)

    @classmethod
    def deleteDB(cls, account, registry=None):
        """Delete the entire database"""
        _db.deleteDB(account, cls, Project, registry)

def project_title_to_id(title):
    return name_to_idstring(title)

special_projects = [ ("Other...", project_title_to_id("Other...")), 
                     ("Industrial Project", project_title_to_id("Industrial Project")) ]

special_projects_dict = {}

def _get_project_by_id(id, project_registry=DEFAULT_PROJECT_REGISTRY):
    """Internal function to find and return a project by ID. Returns None if no such
       project exists."""
    return _db.get_db(Project, id, project_registry)

def _createSpecialProjects(project_registry=DEFAULT_PROJECT_REGISTRY):
    """Internal function used to create the special projects that must exist in the registry"""

    for special_project in special_projects:
        title = special_project[0]
        id = special_project[1]

        project = _get_project_by_id(id, project_registry)

        if not project:
            project = Project( parent = project_key(project_registry),
                               name = title,
                               id = id,
                               bsb_project = False,
                               vat_exempt = False )

            project.put()

        special_projects_dict[title] = id

def list_projects(sorted=True, project_registry=DEFAULT_PROJECT_REGISTRY):
    """Function used to return a list of all projects"""

    _createSpecialProjects()

    projects = Project.getQuery(project_registry).fetch()

    output = []

    if sorted:
        sorted_projects = {}

        for project in projects:
            sorted_projects[project.name] = ProjectInfo(project)

        keys = list(sorted_projects.keys())
        keys.sort()

        for key in keys:
            if not (sorted_projects[key].title in special_projects_dict):
                output.append( sorted_projects[key] )

        for special_project in special_projects:
            if special_project[0] in sorted_projects:
                output.append( sorted_projects[special_project[0]] )

    else:
        for project in projects:
             output.append( ProjectInfo(project) )

    return output

def number_of_projects(project_registry=DEFAULT_PROJECT_REGISTRY):
    """Return the total number of projects"""
    return _db.number_of_items(Project, project_registry)

def _get_project_by_id(id, project_registry=DEFAULT_PROJECT_REGISTRY):
    """Internal function to find and return a project by ID. Returns None if no such
       project exists."""
    return _db.get_db(Project, id, project_registry)

def get_project_by_id(id, project_registry=DEFAULT_PROJECT_REGISTRY):
    """Find and return a project by ID. Returns None if no such
       project exists. Note that this returns a ProjectInfo object"""
    return _db.get_item(Project, ProjectInfo, id, project_registry)

def get_project_by_title(title, project_registry=DEFAULT_PROJECT_REGISTRY):
    """Find and return a project by title. Returns None if no such
       project exists"""
    return get_project_by_id( project_title_to_id(title), project_registry )

def get_project_mapping(registry=DEFAULT_PROJECT_REGISTRY):
    """Return the dictionary mapping project IDs to project names"""
    return _db.get_idstring_to_name_db(Project, registry)

def get_sorted_project_mapping(registry=DEFAULT_PROJECT_REGISTRY):
    """Return a sorted list of all project names, together with their IDs"""
    return _db.get_sorted_names_to_idstring(Project,registry)

class AddProjectError:
    def __init__(self, errors):
        self._errors = errors

    def __str__(self):
        return "AddProjectError(%s)" % repr(self._errors)

    def errors(self):
        return self._errors

def add_project(account, title, bsb_project, vat_exempt, 
                project_registry=DEFAULT_PROJECT_REGISTRY):
    """Function used to add a new project to the system. Note that you have
       to pass in a valid admin account to be able to add projects."""

    if not account.is_admin:
        raise AddProjectError( ["You do not have permission to add the project '%s'" \
                                      % title ] )

    # first, see if the project has already been added
    id = project_title_to_id(title)

    project = get_project_by_id(id)

    if project:
        raise AddProjectError( ["""You cannot add a project with title '%s' as a project
                                   with this title '%s' has already been added.""" % \
                                   (title, project.title) ] )

    errors = []

    # validate that the project title is between 5 and 60 characters in length
    if len(title) < 5:
        errors.append( "You cannot use \"%s\" as a project title as it contains less than 5 characters." % title )

    elif len(title) > 60:
        errors.append( "You cannot use \"%s\" as a project title as it contains more than 60 characters." % title )

    if errors:
        raise AddProjectError(errors)

    # ok, we have validated the input. Now let's try to create the project
    project = Project( parent = project_key(project_registry),
                       name = title,
                       id = id,
                       bsb_project = bsb_project,
                       vat_exempt = vat_exempt )

    project.put()
    _db.changed_idstring_to_name_db(Project,project_registry)

    return

class DeleteProjectError:
    def __init__(self, message):
        self._message = message

    def __str__(self):
        return "DeleteProjectError(%s)" % repr(self._message)

    def error(self):
        return self._message

def delete_project(account, id, project_registry=DEFAULT_PROJECT_REGISTRY):
    """Function that is used to delete a project (by id). Use with caution!"""

    if not account.is_admin:
        raise DeleteProjectError( "You don't have permission to delete a project!" )

    project = _get_project_by_id(id, project_registry)

    if not project:
        raise DeleteProjectError( "Cannot delete project '%s' because it doesn't exist!" % id )

    project.key.delete()
    _db.changed_idstring_to_name_db(Project,project_registry)
