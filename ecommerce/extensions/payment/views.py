""" Views for interacting with the payment processor. """
from decimal import Decimal
import json
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from oscar.apps.order.exceptions import UnableToPlaceOrder
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError
from oscar.apps.shipping import methods as shipping_methods
from oscar.core import prices
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin
from ecommerce.extensions.payment import processors


logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
OrderPlacementMixin = get_class('checkout.mixins', 'OrderPlacementMixin')


class CyberSourceNotifyView(OrderPlacementMixin, FulfillmentMixin, View):
    """
    Accept response from the processor and fulfill the request
    """
    payment_processor = None

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        self.payment_processor = processors.Cybersource()
        return super(CyberSourceNotifyView, self).dispatch(request, *args, **kwargs)

    def add_payment_event(self, event):
        """
        Record a payment event for creation once the order is placed
        """
        # We keep a local cache of (unsaved) payment events
        if self._payment_events is None:  # pylint: disable=access-member-before-definition
            self._payment_events = []  # pylint: disable=attribute-defined-outside-init

        self._payment_events.append(event)

    def handle_payment(self, _order_number, _total, response, basket, **_kwargs):
        """
        Handle any payment processing and record payment sources and events.

        This method is responsible for handling payment and recording the
        payment sources (using the add_payment_source method) and payment
        events (using add_payment_event) so they can be
        linked to the order when it is saved later on.
        """
        source, payment_event = self.payment_processor.handle_processor_response(response, basket=basket)

        self.add_payment_source(source)
        self.add_payment_event(payment_event)

    def handle_successful_order(self, order):
        # TODO Send post_checkout signal
        # TODO Fulfill order
        pass

    def post(self, request):
        """ Handle the response we've been given from the processor. """

        # Note (CCB): No data should be persisted to the database until the payment processor has validated the
        # response's signature. This validation is performed in the handle_payment method. After that method succeeds,
        # the response can be safely assumed to have originated from CyberSource.
        cybersource_response = request.POST.dict()

        # Don't do anything if the response is not valid.
        if not self.payment_processor.is_response_valid(cybersource_response):
            logger.info(u'Received invalid CyberSource response: %s', json.dumps(cybersource_response))
            return HttpResponse()

        basket_id = cybersource_response['req_reference_number']

        try:
            basket_id = int(basket_id)
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
        except (ValueError, ObjectDoesNotExist):
            logger.exception('Received payment for non-existent basket [%s].', basket_id)

            # Set the basket to None to trigger the return logic below, after we record the processor response.
            basket = None

        # Store the response in the database
        transaction_id = cybersource_response['transaction_id']
        ppr = self.payment_processor.record_processor_response(transaction_id, cybersource_response, basket=basket)

        # If we don't have a basket, we cannot continue.
        if not basket:
            return HttpResponse()

        order_number = self.generate_order_number(basket)
        currency = cybersource_response['req_currency']
        _tax = Decimal(cybersource_response.get('req_tax_amount', 0))
        _total = Decimal(cybersource_response['req_amount'])
        order_total = prices.Price(currency=currency, excl_tax=_total - _tax, incl_tax=_total)

        try:
            self.handle_payment(order_number, order_total, response=cybersource_response, basket=basket)
        except PaymentError:
            logger.warning(
                'CyberSource payment failed for basket [%d]. The payment response was recorded in entry [%d]',
                basket.id, ppr.id)
            return HttpResponse()

        # Note (CCB): In the future, if we do end up shipping physical products, we will need to properly implement
        # shipping methods. See http://django-oscar.readthedocs.org/en/latest/howto/how_to_configure_shipping.html.
        shipping_method = shipping_methods.NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)

        billing_address = BillingAddress(first_name=cybersource_response['req_bill_to_forename'],
                                         last_name=cybersource_response['req_bill_to_surname'],
                                         line1=cybersource_response['req_bill_to_address_line1'],
                                         line2=cybersource_response['req_bill_to_address_line2'],

                                         # Oscar uses line4 for city
                                         line4=cybersource_response['req_bill_to_address_city'],
                                         postcode=cybersource_response['req_bill_to_address_postal_code'],
                                         state=cybersource_response['req_bill_to_address_state'],
                                         country=Country.objects.get(
                                             iso_3166_1_a2=cybersource_response['req_bill_to_address_country']))

        try:
            user = basket.owner
            self.handle_order_placement(order_number, user, basket, None, shipping_method, shipping_charge,
                                        billing_address, order_total)
        except UnableToPlaceOrder:
            logger.exception('Payment was received, but an order was not created for basket [%d].', basket.id)
            # Ensure we return, in case future changes introduce post-order placement functionality.
            return HttpResponse()

        return HttpResponse()
