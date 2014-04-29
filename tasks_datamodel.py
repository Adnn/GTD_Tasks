# -*- coding: utf-8 -*-

from __future__ import print_function

import json
import logging
import os
import re

from gtd_model import Item, GtdItem, NextAction, Project, Tag, Plane, Recipient
from common_model import RawValueItem

cb = lambda response: print (u'STATUS: {0}({1}). From cache : {2}'.format(response.status, response.reason, response.fromcache))

##
## Service Providers
##
class FileBackedService(object):
    def __init__(self, service, filepath):
        directory, filename = os.path.split(filepath)
        self.filepath = filepath 
        self.service = service
        if directory and not os.path.exists(directory):
            os.mkdir(directory)
        with open(filepath, 'a+') as datafile :
           datafile.seek(0)
           try:
                logging.info("Successfully loaded existing file cache.")
                self.cache_dictionary = json.load(datafile)
           except ValueError:
                logging.info("File cache was not readable, starts with empty cache.")
                self.cache_dictionary = {}

#    def get(self, key_path):
#        found = reduce(lambda dictionary, key: dictionary.get(key,{}), '/'.split(key_path), self.dictionary)
#        found if found else None
#
#    def set(self, key_path, value):
#        keys = '/'.split(key_path)
#        place = reduce(lambda dictionary, key: dictionary.setdefault(key,{}), keys[:-1], self.dictionary)
#        place[keys[-1:]] = value

    def gen_tasklists(self):
        # \todo Check the ETAG to see if its usefull to go through the loop
        # perhaps it will also save us the pagination ?
        tasklists = self.service.tasklists()
        request = tasklists.list(fields="items/id, items/updated, items/title")
        #request = tasklists.list()
        # {
        #     'id': {
        #         'updated': last_modification_time,
        #         'payload': json
        #     },
        #     ...
        # }
        cache_swap_dict = {}
        tasklists_col = []

        while (request != None):
            tasklists_col_doc = request.execute()
            logging.debug("request returned")

            for item_dict in tasklists_col_doc['items']:
                key_id = item_dict['id']
                #If the value in the cache is up to date, keep it
                cached_date = self.cache_dictionary.get(key_id, {}).get('updated', None)

                if cached_date == item_dict['updated']:
                    logging.info("tasklist {0} up to date. Both: {1}".format(key_id,
                                                                             cached_date))
                    cache_swap_dict[key_id] = self.cache_dictionary[key_id]
                else:
                    logging.info("tasklist {0} not up to date. Cached: {1}, online: {2}".format(key_id, cached_date, item_dict['updated']))
                    cache_swap_dict[key_id] = {'updated': item_dict['updated'], 'payload': {}}

                #And populate a collection of tasklists
                tasklists_col.append(item_dict)
            request = tasklists.list_next(request, tasklists_col_doc)

        self.cache_dictionary = cache_swap_dict
        return tasklists_col
        

    def gen_tasks(self, tasklist_id):
        payload = self.cache_dictionary[tasklist_id]['payload']
        
        if not payload:
            logging.info("Retrieving tasklist {0}, not found in the cache.".format(tasklist_id))
            tasks = self.service.tasks()
            request = tasks.list(tasklist=tasklist_id)
            while (request != None):
                tasks_col_doc = request.execute()
                logging.debug("request returned")
                if not payload:
                    #first time in the body of the while
                    payload.update(tasks_col_doc)
                else:
                    payload['items'].extend(tasks_col_doc['items'])
                request = tasks.list_next(request, tasks_col_doc)

                with open(self.filepath, 'w') as outdatafile:
                    json.dump(self.cache_dictionary, outdatafile)

        return payload['items']

class GreedyService(object):
    def __init__(self, service):
        self.service = service

    def gen_tasklists(self):
        tasklists = self.service.tasklists()
        request = tasklists.list()
        while (request != None):
            tasklists_col_doc = request.execute()
            logging.debug(tasklists_col_doc)
            for item_dict in tasklists_col_doc['items']:
                yield item_dict    
            request = tasklists.list_next(request, tasklists_col_doc)

    def gen_tasks(self, tasklist_id):
        tasks = self.service.tasks()
        request = tasks.list(tasklist=tasklist_id)
        while (request != None):
            tasks_col_doc = request.execute()
            logging.debug(tasks_col_doc)
            for item_dict in tasks_col_doc['items']:
                yield item_dict
            request = tasks.list_next(request, tasks_col_doc)

##
## Google data layer view
##
class DictionaryAsMember(object):
    """ A class to be inherited """
    def __getattr__(self, name):
        try:
            return self.value[name]
        except KeyError:
            raise AttributeError

class TasklistsCollection(object):
    def __init__(self, service):
        self.container = {}

        for tasklist_dict in service.gen_tasklists():
            self.container[tasklist_dict['id']] = Tasklist(service, tasklist_dict)

    def __iter__(self):
        return self.container.itervalues()

    def __str__(self):
        string = ''
        for title, tasklist in self.container.iteritems():
            string += title + ": " + os.linesep + str(tasklist) 

        return string

class Tasklist(DictionaryAsMember):
    def __init__(self, service, tasklist_dict):
        self.container = {}
        self.value = tasklist_dict

        for item_dict in service.gen_tasks(tasklist_dict['id']):
            self.container[item_dict['id']] = Task(item_dict, self)

    def __iter__(self):
        return self.container.itervalues()

    def iteritems(self):
        return self.container.iteritems()

    def __str__(self):
        string = ''
        for task in self.container.itervalues():
            string += '\t' + str(task) + os.linesep

        return string

class Task(DictionaryAsMember):
    def __init__(self, task_dict, tasklist):
        self.value = task_dict
# \todo change name to parent_tasklist
        self.parent = tasklist

    def __unicode__(self):
        return u"{title} (in {tasklist})".format(title=self.value['title'], tasklist=self.parent.value['title'])

    def __str__(self):
        return unicode(self).encode('utf-8')

##
## gTask to GTD adapters
##
class GoogleToGtd:
    ctor_mapping = {u'NEXT': NextAction, u'PROJ': Project,  u'_default': GtdItem}

class NoCategoryException(Exception):
    pass

    
def _extract_element(value_capturing_pattern, element_ctor, text):
    elements = [element_ctor(value) for value in re.findall(value_capturing_pattern, text)]
    return elements, re.sub(value_capturing_pattern, '', text)

def construct_gtd_item(task):
    category, sep, task_text = task.title.partition(':')
    if not task_text:
        raise NoCategoryException(u"Item: {0}".format(task.title))

    tags, task_text = _extract_element('\{(.*?)\}', Tag, task_text)
    planes, task_text = _extract_element('\((.*?)\)', Plane, task_text)
    recipients, task_text = _extract_element('\<(.*?)\>', Recipient, task_text)

    task_text = re.sub('\s+', ' ', task_text).strip()

    item = GoogleToGtd.ctor_mapping.get(category, GtdItem)(task_text, category, task.status==u'needsAction')
    item.tag_list.extend(tags)
    item.plane_list.extend(planes)

    if recipients:
        item.recipient_list = recipients

    return item
    

#If we use .setdefault inline, with a name for the default dictionary
#then everyone share the reference to the same "default" dict (that is mutated along the way)
def _set_default(lookup_dict, task_id):
    return lookup_dict.setdefault(task_id, {u'item':None, u'children':{}})
    

def _is_blank(task):
    return not bool(task.title.strip())


def _populate_lookup(tasklist):
    """ LOOKUP TABLE FORMAT
     {
         task_id: {
             'item':RawValueItem,
             'children': {child_position: child_task_id, ...}
         },
         ...
     }
    
    Deprecated: Special 'item' value "ignored" is reserved to prevent children assignements
    """

    lookup_task_dict = {}
    root_taskids = []

    for task_id, task in [(task_id, task) for task_id, task in tasklist.iteritems()
                                          if not _is_blank(task)]:
        logging.debug(u"Taskid: {0}, Task:{1}".format(task_id, task))

        _set_default(lookup_task_dict, task_id)[u'item'] = RawValueItem(task)

        if u'parent' in task.value:
            # Nb: there is a conflicting parent attribute in task.
            # DO NOT USE task.parent
            _set_default(lookup_task_dict, task.value['parent'])[u'children'] \
                .update({task.position: task_id})
        else:
            #If the item has no parent, it is top level in the current context
            logging.info(u"The task is a parent item.")
            root_taskids.append(task_id)

    return lookup_task_dict, root_taskids


def _assign_children(lookup_task_dict):
    """ Actually set items children, based on the lookup table """
    for gtd_item, child_task_id in [(pair[u'item'], pair[u'children'][child_position])
                                        for pair in lookup_task_dict.itervalues()
                                        for child_position
                                            in sorted(pair[u'children'].iterkeys())]:
        if gtd_item != 'ignored':
            # It is possible that an entry was removed from the lookup table
            # (eg. incorrect format), in which case it was not removed from the parent
            # child list
            if child_task_id in lookup_task_dict:
                logging.debug(u"Adding {0} as a child to {1}".format(child_task_id, gtd_item))
                gtd_item.add_child(lookup_task_dict[child_task_id][u'item'])
 

def get_model_from_gtasks(tasklists_collection):
    root_items = Item()
    for tasklist in tasklists_collection:
        lookup, roots = _populate_lookup(tasklist)

        # Transform the RawValueItems into more specialized items.
        for task_id, item in [(task_id, pair['item']) for task_id, pair in lookup.iteritems()]:
            try:                                    
                lookup[task_id]['item'] = construct_gtd_item(item.rawvalue)
            except NoCategoryException:
                logging.info(u"The task has no category, ignoring it.")
                del lookup[task_id]
                if task_id in roots:
                    roots.remove(task_id)
# \todo could be logically cleaner to remove the task_id from it parent here
                #parent_task_id = tasklist.container[task_id].value['parent']
                #if parent_task_id:
                #    lookup[parent_task_id][children] . . .

#                lookup[task_id]['item'] = 'ignored'

        _assign_children(lookup)

        map(lambda root_id: root_items.add_child(lookup[root_id]['item']), roots)

    return root_items

#def get_model_from_gtasks(tasklists_collection):
#    root_items_list = Item()
#
#    for tasklist in tasklists_collection:
#        # LOOKUP TABLE FORMAT
#        # {
#        #     task_id: {
#        #         'item':gtd_item,
#        #         'children': {child_position: child_task_id, ...}
#        #     },
#        #     ...
#        # }
#        lookup_task_dict = {}
#
#        # Populate the lookup_task_dict
#        for task_id, task in [(task_id, task) for task_id, task in tasklist.iteritems()
#                                              if not _is_blank(task)]:
#            logging.debug(u"Taskid: {0}, Task:{1}".format(task_id, task))
#            try:                                    
#                # the temporary variable is just in case there is an excpetion
#                # we do not want to call set_default
#                gtd_item = construct_gtd_item(task)
#                _set_default(lookup_task_dict, task_id)[u'item'] = gtd_item
#            except NoCategoryException:
#                logging.info(u"The task has no category, ignoring it.")
#                _set_default(lookup_task_dict, task_id)['item'] = 'ignored'
#                continue
#            if u'parent' in task.value:
#                # Nb: there is a conflicting parent attribute in task
#                _set_default(lookup_task_dict, task.value['parent'])[u'children'] \
#                    .update({task.position: task_id})
#            else:
#                #If the item has no parent, it is top level in the current context
#                logging.info(u"The task is a parent item.")
#                root_items_list.add_child(lookup_task_dict[task_id][u'item'])
#
#        # Actually set items children, based on the lookup table
#        for gtd_item, child_task_id in [(pair[u'item'], pair[u'children'][child_position])
#                                            for pair in lookup_task_dict.itervalues()
#                                            for child_position
#                                                in sorted(pair[u'children'].iterkeys())]:
#            if gtd_item != 'ignored':
#                logging.debug(u"Adding {0} as a child to {1}".format(child_task_id, gtd_item))
#                gtd_item.add_child(lookup_task_dict[child_task_id][u'item'])
#
#    return root_items_list

def get_documentation_from_gtasks(tasklists_collection):
    pass 
