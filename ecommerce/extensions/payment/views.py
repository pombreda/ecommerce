"""Views for interacting with payment processors."""
from decimal import Decimal as D

from django.conf import settings
from django.http import HttpResponse
from django.views.generic import View
from oscar.core.loading import get_model, get_class

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors import Cybersource
from ecommerce.extensions.payment.constants import PaymentProcessorConstants as PPC
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.order.constants import OrderStatus as ORDER


Free = get_class('shipping.methods', 'Free')
SourceType = get_model('payment', 'SourceType')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')


class CybersourceNotificationView(EdxOrderPlacementMixin, View):
    """Handle a "merchant notification" from CyberSource.

    CyberSource will notify this endpoint after a transaction completes with information
    about the transaction. If the transaction completed successfully and the parameters
    received are signed correctly, the order associated with the transaction is fulfilled.
    """
    def post(self, request):
        """Parse and verify the integrity of received transaction data.

        If the data does not appear to have been tampered with and the transaction was
        successfully processed, fulfills the order corresponding to the "reference number"
        contained in the received data.

        Returns:
            HTTP_200_OK
        """
        transaction_data = request.POST.dict()
        result = Cybersource().handle_processor_response(transaction_data)

        if result[PPC.SUCCESS]:
            # TODO: Retrieve using reference number from CyberSource
            basket = None

            order_metadata = data.get_order_metadata(basket)

            # Handle payment
            self.handle_payment(
                payment_processor=Cybersource,
                reference=transaction_data[CS.FIELD_NAMES.REQ_REFERENCE_NUMBER],
                total=total
            )

            # Place an order, attempting to fulfill it immediately
            self.handle_order_placement(
                order_number=order_metadata[AC.KEYS.ORDER_NUMBER],
                user=basket.owner,
                basket=basket,
                shipping_address=None,
                shipping_method=order_metadata[AC.KEYS.SHIPPING_METHOD],
                shipping_charge=order_metadata[AC.KEYS.SHIPPING_CHARGE],
                # TODO: Pull from the validated CyberSource parameters
                billing_address=None,
                order_total=order_metadata[AC.KEYS.ORDER_TOTAL]
            )

        return HttpResponse()


class ReceiptView(View):
    """Display a receipt page corresponding to a successful transaction.

    Users can be redirected to this view after successfully completing a transaction.
    """
    def get(self, request, number):
        pass


class CancelView(View):
    """Display a transaction cancellation page.

    Users can be redirected to this view after choosing to cancel a transaction.
    """
    def get(self, request):
        pass
