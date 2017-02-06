from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'gtd_django.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^gtasks/', include('gtasks.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/login/$', 'django.contrib.auth.views.login'),
#    	                        {'template_name': 'gtasks/login.html'}),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout'),
)
