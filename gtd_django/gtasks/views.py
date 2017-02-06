# -*- coding: utf-8 -*-

import os
import logging
import httplib2

from gtd_tasks import tasks_datamodel
from gtd_tasks import visitors
from gtd_tasks.gtd_model import Recipient 

from apiclient.discovery import build
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from gtasks.models import CredentialsModel
from gtd_django import settings
from oauth2client import xsrfutil
from oauth2client.client import flow_from_clientsecrets
from oauth2client.django_orm import Storage

# CLIENT_SECRETS, name of a file containing the OAuth 2.0 information for this
# application, including client_id and client_secret, which are found
# on the API Access tab on the Google APIs
# Console <http://code.google.com/apis/console>
CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), '..', 'client_secrets.json')

FLOW = flow_from_clientsecrets(
    CLIENT_SECRETS,
    scope='https://www.googleapis.com/auth/tasks.readonly',
    redirect_uri='http://localhost:8000/gtasks/oauth2callback')


def get_tasks_service(request):
  storage = Storage(CredentialsModel, 'id', request.user, 'credential')
  credential = storage.get()
  if credential is None or credential.invalid == True:
    FLOW.params['state'] = xsrfutil.generate_token(settings.SECRET_KEY,
                                                   request.user)
    authorize_url = FLOW.step1_get_authorize_url()
    return HttpResponseRedirect(authorize_url)
  else:
    http = httplib2.Http()
    http = credential.authorize(http)
    tasks_service = build("tasks", "v1", http=http)
    return tasks_service

@login_required
def index(request):
    tasks_service = get_tasks_service(request)

    tasklists_collection =  \
        tasks_datamodel.TasklistsCollection(tasks_datamodel.FileBackedService(tasks_service, 'mycache.txt'))
    gtd_item_list = tasks_datamodel.get_model_from_gtasks(tasklists_collection)

    next_lister = visitors.ListNextActions()
    next_lister.visit(gtd_item_list)

    result = visitors.FilterSet(gtd_item_list).filter(visitors.ListNextActions()).filter(visitors.Addresse(Recipient(u"xn")))

    return render_to_response('gtasks/welcome.html', {
                #'tasklists_col': next_lister.next_actions,
                'tasklists_col': result.collection,
                })


class InterlocutorForm(forms.Form):
    interlocutor_filter = forms.BooleanField(required=False) 
    interlocutor = forms.ChoiceField() 

class PlaneForm(forms.Form):
    plane = forms.ChoiceField()

def pair_fix_empty(pair):
    if not pair[1]:
        return (pair[0], pair[0])
    return pair

def generate_forms(documentation, post_data=None):
    if post_data:
        interlocutor_form = InterlocutorForm(post_data)
        plane_form = PlaneForm(post_data)
    else:
        interlocutor_form = InterlocutorForm()
        plane_form = PlaneForm()

    interlocutor_form.fields['interlocutor'].choices = \
        [pair_fix_empty(pair) for pair in [("None", ""), ("Any", "")] + documentation['Interlocutors']]

    interlocutor_form = InterlocutorForm()
    plane_form.fields['plane'].choices = \
        [pair_fix_empty(pair) for pair in [("Any", "")] + documentation['Planes']]

    return {'interlocutor_form': interlocutor_form, 'plane_form': plane_form}


@login_required
def next_actions(request):
    tasks_service = get_tasks_service(request)
    tasklists_collection =  \
        tasks_datamodel.TasklistsCollection(tasks_datamodel.FileBackedService(tasks_service, request.user.username+"_cache.txt"))
    documentation = tasks_datamodel.get_documentation_from_gtasks(tasklists_collection)
    listing = []

    if request.method == 'POST':
        form_dict = generate_forms(documentation, request.POST)
        if len(filter(lambda x: not x.is_valid(), form_dict.itervalues())) == 0: 
            root_item = tasks_datamodel.get_model_from_gtasks(tasklists_collection)
            next_lister = visitors.ListNextActions()
            next_lister.visit(root_item)
            listing = next_lister.result()
    else:
        form_dict = generate_forms(documentation)
#        interlocutor_form = InterlocutorForm()
#        interlocutor_form.fields['interlocutor'].choices = \
#            [pair_fix_empty(pair) for pair in [("None", ""), ("Any", "")] + documentation['Interlocutors']]
#
#        plane_form = PlaneForm()
#        plane_form.fields['plane'].choices = \
#            [pair_fix_empty(pair) for pair in [("Any", "")] + documentation['Planes']]

    return render_to_response('gtasks/list.html',
                              form_dict,
#                              form_dict.update(
#                              {
##                                  'interlocutor_form': interlocutor_form,
##                                  'plane_form': plane_form,
#                                  'tasklists_col': listing,
#                              }),
                              context_instance=RequestContext(request),
                             )

@login_required
def auth_return(request):
    if not xsrfutil.validate_token(settings.SECRET_KEY, request.REQUEST['state'],
                                   request.user):
        return  HttpResponseBadRequest()
    credential = FLOW.step2_exchange(request.REQUEST)
    storage = Storage(CredentialsModel, 'id', request.user, 'credential')
    storage.put(credential)
    return HttpResponseRedirect("gtasks/")

def logout(request):
    logout
