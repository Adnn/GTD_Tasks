# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Command-line skeleton application for Tasks API.
Usage:
  $ python main.py

You can also get help on all the command-line flags the program understands
by running:

  $ python main.py --help

"""

import tasks_datamodel
from tasks_datamodel import TasklistsCollection
import visitors

import argparse
import httplib2
import logging
import os
import sys
import json

from apiclient import discovery
from oauth2client import file
from oauth2client import client
from oauth2client import tools
from apiclient.http import HttpMock


# Parser for command-line arguments.
parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    parents=[tools.argparser])


# CLIENT_SECRETS is name of a file containing the OAuth 2.0 information for this
# application, including client_id and client_secret. You can see the Client ID
# and Client secret on the APIs page in the Cloud Console:
# <https://cloud.google.com/console#/project/187601401574/apiui>
CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'client_secrets.json')

# Set up a Flow object to be used for authentication.
# Add one or more of the following scopes. PLEASE ONLY ADD THE SCOPES YOU
# NEED. For more information on using scopes please see
# <https://developers.google.com/+/best-practices>.
FLOW = client.flow_from_clientsecrets(CLIENT_SECRETS,
  scope=[
      'https://www.googleapis.com/auth/tasks.readonly',
    ],
    message=tools.message_if_missing(CLIENT_SECRETS))


def authorization_procedure(flags=None):
  # If the credentials don't exist or are invalid run through the native client
  # flow. The Storage object will ensure that if successful the good
  # credentials will get written back to the file.
  storage = file.Storage('credentials.dat')
  credentials = storage.get()
  if credentials is None or credentials.invalid:
    credentials = tools.run_flow(FLOW, storage, flags)
  # Create an httplib2.Http object to handle our HTTP requests and authorize it
  # with our good Credentials.
  http = httplib2.Http(cache='.cache')
  #http = HttpMock('tasks_discovery.json', {'status': '200'})
  return credentials.authorize(http)

def main(argv):
    # Parse the command-line flags.
    parser.add_argument('--log', type=str, help="Log level", default='WARNING')
    flags = parser.parse_args(argv[1:])
    http = authorization_procedure(flags)

    numeric_log_level = getattr(logging, flags.log.upper(), None)
    if not isinstance(numeric_log_level, int):
      raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(level=numeric_log_level, format='%(asctime)s %(message)s')

    # Construct the service object for the interacting with the Tasks API.
    task_service = discovery.build('tasks', 'v1', http=http)
    logging.debug("request returned")

    try:
        #Populate the google data layer objects
        tasklists_collection =  \
            TasklistsCollection(tasks_datamodel.FileBackedService(task_service, 'mycache.txt'))
    except client.AccessTokenRefreshError:
        print ("The credentials have been revoked or expired, please re-run"
               "the application to re-authorize")
        return

    gtd_item_list = tasks_datamodel.get_model_from_gtasks(tasklists_collection)
    documentation = tasks_datamodel.get_documentation_from_gtasks(tasklists_collection)

#     next_actions_visitor = tasks_datamodel.ListNextActions()
#     next_actions_visitor.visit(gtd_item_list) 
#     print(next_actions_visitor)
      
    pretty_printer = visitors.PrettyPrinter()
    pretty_printer.visit(gtd_item_list)


# For more information on the Tasks API you can visit:
#
#   https://developers.google.com/google-apps/tasks/firstapp
#
# For more information on the Tasks API Python library surface you
# can visit:
#
#   https://developers.google.com/resources/api-libraries/documentation/tasks/v1/python/latest/
#
# For information on the Python Client Library visit:
#
#   https://developers.google.com/api-client-library/python/start/get_started
if __name__ == '__main__':
  main(sys.argv)
