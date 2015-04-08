from oscar.core.loading import get_model
from oscar.apps.checkout.mixins import OrderPlacementMixin

from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin
from ecommerce.extensions.order.constants import OrderStatus as ORDER
from ecommerce.extensions.payment.constants import PaymentProcessorConstants as PPC


Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class EdxOrderPlacementMixin(OrderPlacementMixin, FulfillmentMixin):
    """Mixin which provides functionality for placing orders.

    Any view class which needs to place an order should use this mixin.
    """
    def handle_payment(self, payment_processor, reference, total):
        """Handle payment processing and record payment sources and events.

        This method is responsible for handling payment and recording the
        payment sources (using the add_payment_source method) and payment
        events (using add_payment_event) so they can be linked to the order
        when it is saved later on.

        In the below, let O represent an order yet to be created.

        Arguments:
            payment_processor (BasePaymentProcessor): The payment processor
                responsible for handling transactions which allow for the
                placement of O.
            reference (unicode): Identifier representing a unique charge in the
                payment processor's system which allows the placement of O.
            total (Price): Represents the amount of money which changed hands in
                order to allow the placement of O.

        Returns:
            None
        """
        source_type, __ = SourceType.objects.get_or_create(name=payment_processor.NAME)
        source = Source(
            source_type=source_type,
            # TODO: Understand if this should be the same as CyberSource reference number
            reference=reference,
            amount_allocated=total.excl_tax
        )
        self.add_payment_source(source)

        # Record payment event
        self.add_payment_event(
            PPC.PAYMENT_EVENT_NAMES.SETTLEMENT,
            total.excl_tax,
            reference=reference
        )

    def handle_successful_order(self, order):
        """Take any actions required after an order has been successfully placed.

        This system is currently designed to sell digital products, so this method
        attempts to immediately fulfill newly-placed orders.
        """
        return self._fulfill_order(order)

    def get_initial_order_status(self, basket):
        """Returns the state in which newly-placed orders are expected to be."""
        return ORDER.OPEN
