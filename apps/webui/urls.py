#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.conf.urls.defaults import *
import apps.webui.views as views

urlpatterns = patterns('',
    # temporary measure until we import magic self-assembling dashboard
    #url(r'^$',     views.dashboard),
    url(r'^ping$', views.check_availability),
    url(r'^uptime$', views.success),
    (r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'webui/login.html'}),
    (r'^accounts/logout/$', 'django.contrib.auth.views.logout', {'template_name': 'webui/loggedout.html'}),
)

