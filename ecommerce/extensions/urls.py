from django.conf.urls import patterns, url, include

from ecommerce.extensions.app import application
from ecommerce.extensions.api.app import application as api
from ecommerce.extensions.payment.app import application as payment


# Uncomment the next two lines to enable the admin
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns(
    '',
    # Uncomment the next line to enable the admin
    # url(r'^admin/', include(admin.site.urls)),

    # Oscar URLs
    url(r'^i18n/', include('django.conf.urls.i18n')),
    # V1 DEPRECATION: Match only v2. This temporarily matches v1 or v2 while we move to v2.
    url(r'^api/v[1-2]/', include(api.urls)),
    url(r'^payment/', include(payment.urls)),

    # This is only here to ensure the login page works for integration tests.
    url(r'^dummy/', lambda r: r, name='password-reset'),

    url(r'', include(application.urls)),
)
