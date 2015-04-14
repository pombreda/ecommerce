"""Exceptions and error messages used by payment processors."""
from oscar.apps.payment.exceptions import GatewayError, PaymentError


class InvalidSignatureError(GatewayError):
    """ The signature of the payment processor's response is invalid. """
    pass


class InvalidCyberSourceDecision(GatewayError):
    """ The decision returned by CyberSource was not recognized. """
    pass


class PartialAuthorizationError(PaymentError):
    """ The amount authorized by the payment processor differs from the requested amount. """
    pass
