from __future__ import absolute_import

import os

from ecommerce.settings.base import *


# TEST SETTINGS
INSTALLED_APPS += (
    'django_nose',
)

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'


class DisableMigrations(object):
    """Override method calls on the MIGRATION_MODULES dictionary.

    If the `makemigrations` command has not been run for an app, the
    `migrate` command treats that app as unmigrated, creating tables
    directly from the models just like the now-defunct `syncdb` command
    used to do. These overrides are used to force Django to treat apps
    in this project as unmigrated.

    Django 1.8 features the `--keepdb` flag for exactly this purpose,
    but we don't have that luxury in 1.7.

    For more context, see http://goo.gl/Fr4qyE.
    """
    def __contains__(self, item):
        """Make it appear as if all apps are contained in the dictionary."""
        return True

    def __getitem__(self, item):
        """Force Django to look for migrations in a nonexistent package."""
        return 'notmigrations'

if str(os.environ.get('DISABLE_MIGRATIONS')) == 'True':
    MIGRATION_MODULES = DisableMigrations()
# END TEST SETTINGS


# IN-MEMORY TEST DATABASE
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
        'ATOMIC_REQUESTS': True,
    },
}
# END IN-MEMORY TEST DATABASE


# URL CONFIGURATION
# Do not include a trailing slash.
LMS_URL_ROOT = 'http://127.0.0.1:8000'

# The location of the LMS heartbeat page
LMS_HEARTBEAT_URL = LMS_URL_ROOT + '/heartbeat'

# The location of the LMS student dashboard
LMS_DASHBOARD_URL = LMS_URL_ROOT + '/dashboard'
# END URL CONFIGURATION


# AUTHENTICATION
ENABLE_AUTO_AUTH = True

JWT_AUTH['JWT_SECRET_KEY'] = 'insecure-secret-key'
# END AUTHENTICATION


# ORDER PROCESSING
ENROLLMENT_API_URL = LMS_URL_ROOT + '/api/enrollment/v1/enrollment'

EDX_API_KEY = 'replace-me'
# END ORDER PROCESSING


# PAYMENT PROCESSING
PAYMENT_PROCESSORS = (
    'ecommerce.extensions.payment.processors.Cybersource',
)

PAYMENT_PROCESSOR_CONFIG = {
    'cybersource': {
        'profile_id': 'fake-profile-id',
        'access_key': 'fake-access-key',
        'secret_key': 'fake-secret-key',
        'payment_page_url': 'https://replace-me/',
        # TODO: XCOM-202 must be completed before any other receipt page is used.
        # By design this specific receipt page is expected.
        'receipt_page_url': 'https://replace-me/verify_student/payment-confirmation/',
        'cancel_page_url': 'https://replace-me/',
    }
}
# END PAYMENT PROCESSING
