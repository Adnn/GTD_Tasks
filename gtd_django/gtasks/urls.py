from django.conf.urls import patterns, include, url

import os


urlpatterns = patterns('',
    # Example:
    (r'^$', 'gtasks.views.index'),
    (r'^oauth2callback', 'gtasks.views.auth_return'),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs'
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    (r'^static/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': os.path.join(os.path.dirname(__file__), 'static')
}),
)
