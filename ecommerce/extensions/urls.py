from django.conf.urls import patterns, url, include

from ecommerce.extensions.app import application
from ecommerce.extensions.api.app import application as api
from ecommerce.extensions.payment.app import application as payment


urlpatterns = patterns(
    '',
    url(r'^api/v1/', include(api.urls)),
    url(r'^payment/', include(payment.urls)),
    url(r'', include(application.urls)),
)
