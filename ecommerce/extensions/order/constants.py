"""Order constants."""

ORDER_NUMBER_PATTERN = r'(?P<number>[-\w]+)'


class OrderStatus(object):
    """Constants representing all known order statuses."""
    OPEN = 'Open'
    FULFILLMENT_ERROR = 'Fulfillment Error'
    COMPLETE = 'Complete'
    REFUNDED = 'Refunded'


class LineStatus(object):
    """Constants representing all known line statuses."""
    OPEN = 'Open'
    FULFILLMENT_CONFIGURATION_ERROR = 'Fulfillment Configuration Error'
    FULFILLMENT_NETWORK_ERROR = 'Fulfillment Network Error'
    FULFILLMENT_TIMEOUT_ERROR = 'Fulfillment Timeout Error'
    FULFILLMENT_SERVER_ERROR = 'Fulfillment Server Error'
    COMPLETE = 'Complete'
    REFUNDED = 'Refunded'
    REVOKE_CONFIGURATION_ERROR = 'Revoke Configuration Error'
    REVOKE_NETWORK_ERROR = 'Revoke Network Error'
    REVOKE_TIMEOUT_ERROR = 'Revoke Timeout Error'
    REVOKE_SERVER_ERROR = 'Revoke Server Error'
