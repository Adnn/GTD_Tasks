from __future__ import print_function

import json
import logging
import os
import re

from gtd_model import GtdItem, NextAction, Project, Tag, Plane, Recipient

cb = lambda response: print (u'STATUS: {0}({1}). From cache : {2}'.format(response.status, response.reason, response.fromcache))

##
## Cache
##
#class FileDataStore(object):
#    def __init__(self, directory)
#        if not os.path.exists(directory):
#            os.makedires(directory)
#        self.directory = directory
#
#    def load():
#        data_file = open('datafile')
#    
#       
#     

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

    def get(self, key_path):
        found = reduce(lambda dictionary, key: dictionary.get(key,{}), '/'.split(key_path), self.dictionary)
        found if found else None

    def set(self, key_path, value):
        keys = '/'.split(key_path)
        place = reduce(lambda dictionary, key: dictionary.setdefault(key,{}), keys[:-1], self.dictionary)
        place[keys[-1:]] = value

    def gen_tasklists(self):
        # \todo Check the ETAG to see if its usefull to go through the loop
        # perhaps it will also save us the pagination ?
        tasklists = self.service.tasklists()
        request = tasklists.list()
        # { 'id': {'updated': last_modification_time, 'payload': json}, ... }
        cache_swap_dict = {}
        tasklists_col = []
        while (request != None):
            tasklists_col_doc = request.execute()
            for item_dict in tasklists_col_doc['items']:
                key_id = item_dict['id']
                #If the value in the cache is up to date, keep it
                cached_date = self.cache_dictionary.get(key_id, {}).get('updated', None)
                if cached_date == item_dict['updated']:
                    logging.info("tasklist {0} up to date. Both: {1}".format(key_id, cached_date))
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
                if not payload:
                    #first time in the body of the while
                    payload.update(tasks_col_doc)
                else:
                    payload['items'].update(tasks_col_doc['items'])
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
        self.parent = tasklist

    def __unicode__(self):
        return u"{title} (in {tasklist})".format(title=self.value['title'], tasklist=self.parent.value['title'])

    def __str__(self):
        return unicode(self).encode('utf-8')

#    def __repr__(self):
#        return str(self)

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
    
def is_blank(task):
    return not bool(task.title.strip())

def get_model_from_gtasks(service):
    #Populate the google data layer objects
    tasklists_collection = TasklistsCollection(service)

    root_items_list = GtdItem('',  '', False)

    for tasklist in tasklists_collection:
        #Populate the lookup table
        # format: {task_id: {'item':gtd_item, 'children':{child_position: child_task_id, ...}}, ...}
        lookup_task_dict = {}
        for task_id, task in [(task_id, task) for task_id, task in tasklist.iteritems()
                                              if not is_blank(task)]:
            logging.debug(u"Taskid: {0}, Task:{1}".format(task_id, task))
            try:                                    
                # the temporary variable is just in case there is an excpetion
                # we do not want to call set_default
                gtd_item = construct_gtd_item(task)
                _set_default(lookup_task_dict, task_id)[u'item'] = gtd_item
            except NoCategoryException:
                logging.info(u"The task has no category, ignoring it.")
                _set_default(lookup_task_dict, task_id)['item'] = 'ignored'
                continue
            if u'parent' in task.value:
                _set_default(lookup_task_dict, task.value['parent'])[u'children'].update({task.position:task_id})
            else:
                #If the item has no parent, it is top level in the current context
                logging.info(u"The task is a parent item.")
                root_items_list.add_child(lookup_task_dict[task_id][u'item'])

            for task_value in lookup_task_dict.itervalues():
                if task_value['item'] is None:
                    pass

        #Populate each item children, based on the lookup table
        logging.info(u"Populate each item children")
        for gtd_item, child_task_id in [(pair[u'item'], pair[u'children'][child_position])
                                            for pair in lookup_task_dict.itervalues()
                                            for child_position in sorted(pair[u'children'].iterkeys())]:
            if gtd_item != 'ignored':
                logging.debug(u"Adding {0} as a child to {1}".format(child_task_id, gtd_item))
                gtd_item.add_child(lookup_task_dict[child_task_id][u'item'])

    return root_items_list
