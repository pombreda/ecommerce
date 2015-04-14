""" Tests of the Payment Views. """

import ddt
from django.core.urlresolvers import reverse
from django.test import TestCase
import mock
from oscar.apps.order.exceptions import UnableToPlaceOrder
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.extensions.payment.processors import Cybersource
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin, CyberSourceMixin
from ecommerce.extensions.payment.views import CyberSourceNotifyView


Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
SourceType = get_model('payment', 'SourceType')


@ddt.ddt
class CyberSourceNotifyViewTestCase(CyberSourceMixin, PaymentEventsMixin, TestCase):
    """ Test processing of CyberSource notifications. """

    def setUp(self):
        super(CyberSourceNotifyViewTestCase, self).setUp()

        self.user = factories.UserFactory()
        factories.UserAddressFactory(user=self.user)

        self.basket = factories.create_basket()
        self.basket.owner = self.user
        self.basket.freeze()

        self.processor = Cybersource()
        self.processor_name = self.processor.NAME

    def assert_payment_data_recorded(self, notification):
        """ Ensure PaymentEvent, PaymentProcessorResponse, and Source objects are created for the basket. """

        # Ensure the response is stored in the database
        self.assert_processor_response_recorded(self.processor_name, notification[u'transaction_id'], notification,
                                                basket=self.basket)

        # Validate a payment Source was created
        reference = notification[u'transaction_id']
        source_type = SourceType.objects.get(code=self.processor_name)
        self.assert_payment_source_exists(self.basket, source_type, reference)

        # Validate that PaymentEvents exist
        paid_type = PaymentEventType.objects.get(code='paid')
        self.assert_payment_event_exists(self.basket, paid_type, reference, self.processor_name)

    def test_accepted(self):
        """
        When payment is accepted, the following should occur:
            1. The response is recorded and PaymentEvent/Source objects created.
            2. An order for the corresponding basket is created.
            3. The order is fulfilled.
        """

        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        address = self.user.addresses.first()
        notification = self.generate_notification(self.processor.secret_key, self.basket, billing_address=address)
        response = self.client.post(reverse('cybersource_notify'), notification)

        # The view should always return 200
        self.assertEqual(response.status_code, 200)

        # Validate that a new order exists
        order = Order.objects.get(basket=self.basket)
        self.assertIsNotNone(order, 'No order was created for the basket after payment.')

        self.assert_payment_data_recorded(notification)

        # TODO Check the order's lines

    @ddt.data('CANCEL', 'DECLINE', 'ERROR', 'blah!')
    def test_not_accepted(self, decision):
        """
        When payment is NOT accepted, the processor's response should be saved to the database. An order should NOT
        be created.
        """

        notification = self.generate_notification(self.processor.secret_key, self.basket, decision=decision)
        response = self.client.post(reverse('cybersource_notify'), notification)

        # The view should always return 200
        self.assertEqual(response.status_code, 200)

        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        # Ensure the response is stored in the database
        self.assert_processor_response_recorded(self.processor_name, notification[u'transaction_id'], notification,
                                                basket=self.basket)

    def test_unable_to_place_order(self):
        """ When payment is accepted, but an order cannot be placed, log an error and return HTTP 200. """

        address = self.user.addresses.first()
        notification = self.generate_notification(self.processor.secret_key, self.basket, billing_address=address)

        with mock.patch.object(CyberSourceNotifyView, 'handle_order_placement', side_effect=UnableToPlaceOrder):
            response = self.client.post(reverse('cybersource_notify'), notification)

        # The view should always return 200
        self.assertEqual(response.status_code, 200)

        self.assert_processor_response_recorded(self.processor_name, notification[u'transaction_id'], notification,
                                                basket=self.basket)

    @ddt.data('abc', '1986')
    def test_invalid_basket(self, basket_id):
        """ When payment is accepted for a non-existent basket, log an error and record the response. """

        address = self.user.addresses.first()
        notification = self.generate_notification(self.processor.secret_key, self.basket, billing_address=address,
                                                  req_reference_number=basket_id)
        response = self.client.post(reverse('cybersource_notify'), notification)

        self.assertEqual(response.status_code, 200)
        self.assert_processor_response_recorded(self.processor_name, notification[u'transaction_id'], notification)

    def test_invalid_signature(self):
        """
        If the response signature is invalid, the view should return a 200. NO data should be persisted to the database.
        """
        notification = self.generate_notification(self.processor.secret_key, self.basket)
        notification[u'signature'] = u'Tampered'
        response = self.client.post(reverse('cybersource_notify'), notification)

        # The view should always return 200
        self.assertEqual(response.status_code, 200)

        # The basket should not have an associated order or processor response if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())
        self.assertFalse(PaymentProcessorResponse.objects.filter(basket=self.basket).exists())
