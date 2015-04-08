"""Functions used for data retrieval and manipulation by the API."""
import logging

from oscar.core.loading import get_model, get_class

from ecommerce.extensions.api import errors
from ecommerce.extensions.api.constants import APIConstants as AC


logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
Product = get_model('catalogue', 'Product')
ShippingEventType = get_model('order', 'ShippingEventType')

Free = get_class('shipping.methods', 'Free')
Selector = get_class('partner.strategy', 'Selector')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')


def get_basket(user):
    """Retrieve the basket belonging to the indicated user.

    If no such basket exists, create a new one. If multiple such baskets exist,
    merge them into one.
    """
    editable_baskets = Basket.objects.filter(owner=user, status__in=Basket.editable_statuses)
    if len(editable_baskets) == 0:
        basket = Basket.objects.create(owner=user)
    else:
        stale_baskets = list(editable_baskets)
        basket = stale_baskets.pop(0)
        for stale_basket in stale_baskets:
            # Don't add line quantities when merging baskets
            basket.merge(stale_basket, add_quantities=False)

    # Assign the appropriate strategy class to the basket
    basket.strategy = Selector().strategy(user=user)

    return basket


def get_product(sku):
    """Retrieve the product corresponding to the provided SKU."""
    try:
        return Product.objects.get(stockrecords__partner_sku=sku)
    except Product.DoesNotExist:
        raise errors.ProductNotFoundError(
            errors.PRODUCT_NOT_FOUND_DEVELOPER_MESSAGE.format(sku=sku)
        )


# TODO: Move to fulfillment app
def get_shipping_event_type(name):
    """Retrieve the shipping event type corresponding to the provided name."""
    try:
        return ShippingEventType.objects.get(name=name)
    except ShippingEventType.DoesNotExist:
        raise errors.ShippingEventNotFoundError(
            errors.SHIPPING_EVENT_NOT_FOUND_MESSAGE.format(name=name)
        )


def get_order_metadata(basket):
    """Retrieve metadata required to place an order.

    Arguments:
        basket (Basket): The basket whose contents are being ordered.

    Returns:
        dict: Containing an order number, a shipping method, a shipping charge,
            and a Price object representing the order total.
    """
    number = OrderNumberGenerator().order_number(basket)

    shipping_method = Free()
    shipping_charge = shipping_method.calculate(basket)
    total = OrderTotalCalculator().calculate(basket, shipping_charge)

    logger.info(
        u"Preparing to place order [%s] for the contents of basket [%d]",
        number,
        basket.id,
    )

    metadata = {
        AC.KEYS.ORDER_NUMBER: number,
        AC.KEYS.SHIPPING_METHOD: shipping_method,
        AC.KEYS.SHIPPING_CHARGE: shipping_charge,
        AC.KEYS.ORDER_TOTAL: total,
    }

    return metadata
