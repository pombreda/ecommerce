"""HTTP endpoints for interacting with Oscar."""
import logging

from django.conf import settings
from django.http import Http404
from oscar.core.loading import get_class, get_classes, get_model
from rest_framework import status
from rest_framework.generics import (UpdateAPIView, RetrieveAPIView,
    CreateAPIView, ListCreateAPIView, ListAPIView)
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from ecommerce.extensions.api import data, errors, serializers
from ecommerce.extensions.api.throttling import BasketsThrottle, OrdersThrottle
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.order.constants import OrderStatus as ORDER
from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin
from ecommerce.extensions.payment.helpers import get_default_payment_processor
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin


logger = logging.getLogger(__name__)

Free = get_class('shipping.methods', 'Free')
EventHandler = get_class('order.processing', 'EventHandler')
Order = get_model('order', 'Order')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')

# pylint: disable=unbalanced-tuple-unpacking
OrderCreator, OrderNumberGenerator = get_classes('order.utils', ['OrderCreator', 'OrderNumberGenerator'])


class BasketCreateAPIView(EdxOrderPlacementMixin, CreateAPIView):
    """Endpoint for creating baskets.

    If requested, performs checkout operations on baskets, placing an order if
    the contents of the basket are free, and generating payment parameters otherwise.
    """
    throttle_classes = (BasketsThrottle,)
    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        """Add a product to the authenticated user's basket.

        Expects a SKU string to be provided in the request body, which is
        used to populate the user's basket with the corresponding product.

        The caller indicates whether checkout should occur by providing
        a Boolean value. If checkout operations are requested and the
        contents of the user's basket are free, an order is placed immediately.
        If checkout operations are requested but the contents of the user's
        basket are not free, payment parameters are generated instead of placing
        an order.

        Protected by JWT authentication. Consuming services (e.g., the LMS)
        must authenticate themselves by passing a JWT in the Authorization
        HTTP header, prepended with the string 'JWT '. The JWT payload should
        contain user details. At a minimum, these details must include a
        username; providing an email is recommended.

        Arguments:
            request (HttpRequest): With parameters 'sku' and 'checkout' in the body.

        Returns:
            HTTP_200_OK if a basket was created successfully; the basket is serialized in
                the response along with either an associated order (None if one wasn't
                placed) or payment parameters (None if they were never generated).
            HTTP_400_BAD_REQUEST if the client provided invalid data or attempted to add an
                unavailable product to their basket, with reason for the failure in JSON format.
            HTTP_401_UNAUTHORIZED if an unauthenticated request is denied permission to access
                the endpoint.
            HTTP_429_TOO_MANY_REQUESTS if the client has made requests at a rate exceeding that
                allowed by the BasketsThrottle.

        Examples:
            Create a basket for the user with username 'Saul' as follows. Successful fulfillment
            requires that a user with username 'Saul' exists on the LMS, and that EDX_API_KEY be
            configured within both the LMS and the ecommerce service.

            >>> url = 'http://localhost:8002/api/v1/baskets/'
            >>> token = jwt.encode({'username': 'Saul', 'email': 'saul@bettercallsaul.com'}, 'insecure-secret-key')
            >>> headers = {
                'content-type': 'application/json',
                'Authorization': 'JWT ' + token
            }

            If checkout is not desired:

            >>> data = {'sku': 'SOME-SEAT', 'checkout': False}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> json.loads(response.content)
            {
                u'currency': u'USD',
                u'date_created': u'2015-04-08T00:03:52.681493Z',
                u'id': 7,
                u'lines': [{
                    u'description': u'Free Seat in Awesome Course',
                    u'line_price_excl_tax': 0.0,
                    u'quantity': 1,
                    u'unit_price_excl_tax': 0.0
                }],
                u'order': None,
                u'payment_parameters': None,
                u'status': u'Open',
                u'total_excl_tax': 0.0
            }

            If the product with SKU 'FREE-SEAT' is free and checkout is desired:

            >>> data = {'sku': 'FREE-SEAT', 'checkout': True}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> json.loads(response.content)
            {
                u'currency': u'USD',
                u'date_created': u'2015-04-08T00:05:54.641291Z',
                u'id': 8,
                u'lines': [{
                    u'description': u'Free Seat in Awesome Course',
                    u'line_price_excl_tax': 0.0,
                    u'quantity': 1,
                    u'unit_price_excl_tax': 0.0
                }],
                u'order': {
                    u'billing_address': None,
                    u'currency': u'USD',
                    u'date_placed': u'2015-04-08T00:05:54.761243Z',
                    u'lines': [{
                        u'description': u'Free Seat in Awesome Course',
                        u'line_price_excl_tax': 0.0,
                        u'quantity': 1,
                        u'status': u'Complete',
                        u'title': u'Free Seat in Awesome Course',
                        u'unit_price_excl_tax': 0.0
                    }],
                    u'number': u'OSCR-100008',
                    u'payment_processor': u'',
                    u'sources': [],
                    u'status': u'Complete',
                    u'total_excl_tax': 0.0
                },
                u'payment_parameters': None,
                u'status': u'Frozen',
                u'total_excl_tax': 0.0
            }

            If the product with SKU 'PAID-SEAT' is not free and checkout is desired:

            >>> data = {'sku': 'PAID-SEAT', 'checkout': True}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> json.loads(response.content)
            {
                u'currency': u'USD',
                u'date_created': u'2015-04-08T00:06:55.433634Z',
                u'id': 9,
                u'lines': [{
                    u'description': u'Paid Seat in Awesome Course',
                    u'line_price_excl_tax': 10.0,
                    u'quantity': 1,
                    u'unit_price_excl_tax': 10.0
                }],
                u'order': None,
                u'payment_parameters': {
                    u'access_key': u'fake-access-key',
                    u'amount': u'10.00',
                    u'currency': u'USD',
                    u'locale': u'en-us',
                    u'payment_method': u'card',
                    u'profile_id': u'fake-profile-id',
                    u'reference_number': u'9',
                    u'signature': u'byU57lt+jdf8Iv5/2+uedrs1uEgJ+gHFUFZ4w9o/Dos=',
                    u'signed_date_time': u'2015-04-08T00:06:55.58Z',
                    u'signed_field_names': (u'access_key,profile_id,reference_number,transaction_uuid,'
                        u'transaction_type,payment_method,currency,amount,locale,signed_date_time,'
                        u'unsigned_field_names,signed_field_names'),
                    u'transaction_type': u'sale',
                    u'transaction_uuid': u'9d7d45e0227d4b76818f5af49b846f9c',
                    u'unsigned_field_names': u''
                },
                u'status': u'Frozen',
                u'total_excl_tax': 10.0
            }
        """
        sku = request.data.get('sku')
        if sku:
            try:
                product = data.get_product(sku)
            except errors.ProductNotFoundError as error:
                return self._report_bad_request(error.message, errors.PRODUCT_NOT_FOUND_USER_MESSAGE)
        else:
            return self._report_bad_request(
                errors.SKU_NOT_FOUND_DEVELOPER_MESSAGE,
                errors.SKU_NOT_FOUND_USER_MESSAGE
            )

        basket = data.get_basket(request.user)
        availability = basket.strategy.fetch_for_product(product).availability

        if not availability.is_available_to_buy:
            return self._report_bad_request(availability.message, errors.PRODUCT_UNAVAILABLE_USER_MESSAGE)

        basket.add_product(product)
        logger.info(
            u"Added product with SKU [%s] to basket [%d]",
            sku,
            basket.id,
        )

        is_checkout = request.data.get('checkout')
        response_data = self._checkout(basket) if is_checkout is True else self._generate_basic_response(basket)

        return Response(response_data, status=status.HTTP_200_OK)

    def _report_bad_request(self, developer_message, user_message):
        """Log error and create a response containing conventional error messaging."""
        logger.error(developer_message)
        return Response(
            {
                'developer_message': developer_message,
                'user_message': user_message
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def _generate_basic_response(self, basket):
        """Create a dictionary to be used as response data.

        The dictionary contains placeholders for a serialized order and payment parameters.

        Arguments:
            basket (Basket): The basket which should be serialized in the response data.

        Returns:
            dict: Basic response data.
        """
        response_data = serializers.BasketSerializer(basket).data
        response_data[AC.KEYS.PAYMENT_PARAMETERS] = None
        response_data[AC.KEYS.ORDER] = None

        return response_data

    def _checkout(self, basket):
        """Perform checkout operations for the given basket.

        If the contents of the basket are free, places an order immediately. Otherwise,
        generates a set of payment parameters to be sent to a payment processor.

        To prevent stale items from ending up in a basket at checkout, baskets should
        always be frozen during checkout. Baskets with a status of 'Frozen' or 'Submitted'
        are not retrieved when fetching a basket for the user. 

        Arguments:
            basket (Basket): The basket on which to perform checkout operations.

        Returns:
            dict: Response data.
        """
        basket.freeze()
        logger.info(
            u"Froze basket [%d]",
            basket.id,
        )

        response_data = self._generate_basic_response(basket)

        if basket.total_excl_tax == AC.FREE:
            order_metadata = data.get_order_metadata(basket)

            # Place an order, attempting to fulfill it immediately
            order = self.handle_order_placement(
                order_number=order_metadata[AC.KEYS.ORDER_NUMBER],
                user=basket.owner,
                basket=basket,
                shipping_address=None,
                shipping_method=order_metadata[AC.KEYS.SHIPPING_METHOD],
                shipping_charge=order_metadata[AC.KEYS.SHIPPING_CHARGE],
                billing_address=None,
                order_total=order_metadata[AC.KEYS.ORDER_TOTAL]
            )

            response_data[AC.KEYS.ORDER] = serializers.OrderSerializer(order).data
        else:
            payment_processor = get_default_payment_processor()
            response_data[AC.KEYS.PAYMENT_PARAMETERS] = payment_processor().generate_transaction_parameters(basket)

        return response_data


class RetrieveOrderView(RetrieveAPIView):
    """Allow the viewing of orders.

    Given an order number, allow the viewing of the corresponding order. This endpoint will only return an order if
    it in a PAID state, or is in a later state in the order life cycle (COMPLETE, FULFILLMENT_ERROR, REFUNDED).
    This endpoint will return a 404 response status if no order is found. This endpoint will only return orders
    associated with the authenticated user.

    Returns:
        Order: The requested order.

    Example:
        >>> url = 'http://localhost:8002/api/v1/orders/100022'
        >>> headers = {
            'content-type': 'application/json',
            'Authorization': 'JWT ' + token
        }
        >>> response = requests.get(url, headers=headers)
        >>> response.status_code
        200
        >>> response.content
        '{
            "currency": "USD",
            "date_placed": "2015-02-27T18:42:34.017218Z",
            "lines": [
                {
                    "description": "Seat in DemoX Course with Honor Certificate",
                    "status": "Complete",
                    "title": "Seat in DemoX Course with Honor Certificate",
                    "unit_price_excl_tax": 0.0
                }
            ],
            "number": "OSCR-100022",
            "status": "Complete",
            "total_excl_tax": 0.0
        }'
    """
    throttle_classes = (OrdersThrottle,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer
    lookup_field = 'number'
    queryset = Order.objects.all()

    def get_object(self):
        """Retrieve the order for this request.

        Retrieves the associated order. It it is associated with the authenticated user, returns it. Otherwise,
        raises an Http404 exception.

        Returns:
            Order: The associated order.

        Raises:
            Http404: Returns a 404 not found exception if the requested order cannot be found or
                is not associated with the authenticated user.
        """
        order = super(RetrieveOrderView, self).get_object()
        if order and order.user.username == self.request.user.username:
            return order
        else:
            raise Http404


class OrderListAPIView(ListAPIView):
    """
    Endpoint for listing orders.

    Results are ordered with the newest order being the first in the list of results.
    """
    throttle_classes = (OrdersThrottle,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer

    def get_queryset(self):
        return self.request.user.orders.order_by('-date_placed')


# V1 DEPRECATION: Remove OrderListCreateAPIView.
class OrderListCreateAPIView(FulfillmentMixin, ListCreateAPIView):
    """
    Endpoint for listing or creating orders.

    When listing orders, results are ordered with the newest order being the first in the list of results.
    """
    throttle_classes = (OrdersThrottle,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer

    FREE = 0

    def get_queryset(self):
        return self.request.user.orders.order_by('-date_placed')

    def create(self, request, *args, **kwargs):
        """Add one product to a basket, then prepare an order.

        PENDING DEPRECATION. Please use BasketCreateAPIView instead.

        Protected by JWT authentication. Consuming services (e.g., the LMS)
        must authenticate themselves by passing a JWT in the Authorization
        HTTP header, prepended with the string 'JWT'. The JWT payload should
        contain user details. At a minimum, these details must include a
        username; providing an email is recommended.

        Expects a SKU to be provided in the POST data, which is then used
        to populate the user's basket with the corresponding product, freeze
        that basket, and prepare an order using that basket. If the order
        total is zero (i.e., the ordered product was free), an attempt to
        fulfill the order is made.

        Arguments:
            request (HttpRequest)

        Returns:
            HTTP_200_OK if the order was created successfully, with order data in JSON format
            HTTP_400_BAD_REQUEST if the client has provided invalid data or has attempted
                to add an unavailable product to their basket, with reason for the failure
                in JSON format
            HTTP_401_UNAUTHORIZED if an unauthenticated request is denied permission to access
                the endpoint
            HTTP_429_TOO_MANY_REQUESTS if the client has made requests at a rate exceeding that
                allowed by the OrdersThrottle

        Example:
            Create an order for the user with username 'Saul' as follows. (Successful fulfillment
            requires that a user with username 'Saul' exists on the LMS, and that EDX_API_KEY be
            configured on both Oscar and the LMS.)

            >>> url = 'http://localhost:8002/api/v1/orders/'
            >>> data = {'sku': 'SEAT-HONOR-EDX-DEMOX-DEMO-COURSE'}
            >>> token = jwt.encode({'username': 'Saul', 'email': 'saul@bettercallsaul.com'}, 'insecure-secret-key')
            >>> headers = {
                'content-type': 'application/json',
                'Authorization': 'JWT ' + token
            }
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> response.status_code
            200
            >>> response.content
            '{
                "currency": "USD",
                "date_placed": "2015-02-27T18:42:34.017218Z",
                "lines": [
                    {
                        "description": "Seat in DemoX Course with Honor Certificate",
                        "status": "Complete",
                        "title": "Seat in DemoX Course with Honor Certificate",
                        "unit_price_excl_tax": 0.0
                    }
                ],
                "number": "OSCR-100021",
                "status": "Complete",
                "total_excl_tax": 0.0
            }'
        """
        sku = request.data.get('sku')
        if sku:
            try:
                product = data.get_product(sku)
            except errors.ProductNotFoundError as error:
                return self._report_bad_request(error.message, errors.PRODUCT_NOT_FOUND_USER_MESSAGE)
        else:
            return self._report_bad_request(
                errors.SKU_NOT_FOUND_DEVELOPER_MESSAGE,
                errors.SKU_NOT_FOUND_USER_MESSAGE
            )

        basket = data.get_basket(request.user)
        availability = basket.strategy.fetch_for_product(product).availability

        # If an exception is raised before order creation but after basket creation,
        # an empty basket for the user will be left in the system. However, if this
        # user attempts to order again, the `get_basket` utility will merge all old
        # baskets with a new one, returning a fresh basket.
        if not availability.is_available_to_buy:
            return self._report_bad_request(availability.message, errors.PRODUCT_UNAVAILABLE_USER_MESSAGE)

        payment_processor = get_default_payment_processor()

        order = self._prepare_order(basket, product, sku, payment_processor)
        if order.total_excl_tax == self.FREE:
            logger.info(
                u"Attempting to immediately fulfill order [%s] totaling [%.2f %s]",
                order.number,
                order.total_excl_tax,
                order.currency,
            )

            order = self._fulfill_order(order)

        order_data = self._assemble_order_data(basket, payment_processor)

        return Response(order_data, status=status.HTTP_200_OK)

    def _report_bad_request(self, developer_message, user_message):
        """Log error and create a response containing conventional error messaging."""
        logger.error(developer_message)
        return Response(
            {
                'developer_message': developer_message,
                'user_message': user_message
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def _prepare_order(self, basket, product, sku, payment_processor):
        """Prepare an order consisting of a single product for a user."""
        # Baskets with a status of 'Frozen' or 'Submitted' are not retrieved at the
        # start of a new order. To prevent stale items from ending up in the basket
        # at the start of an order, we want to guarantee that this endpoint creates
        # new orders iff the basket in use is frozen first. Since ATOMIC_REQUESTS is
        # assumed to be enabled, wrapping this block with an `atomic()` context
        # manager to ensure atomicity would be redundant.
        basket.add_product(product)
        basket.freeze()

        logger.info(
            u"Added product [SKU: %s] to basket [%d]",
            sku,
            basket.id,
        )

        order_metadata = data.get_order_metadata(basket)

        order = OrderCreator().place_order(
            basket,
            order_metadata[AC.KEYS.ORDER_TOTAL],
            order_metadata[AC.KEYS.SHIPPING_METHOD],
            order_metadata[AC.KEYS.SHIPPING_CHARGE],
            user=basket.owner,
            order_number=order_metadata[AC.KEYS.ORDER_NUMBER],
            status=ORDER.OPEN
        )

        logger.info(
            u"Created order [%s] totaling [%.2f %s] using basket [%d]; payment to be processed by [%s]",
            order.number,
            order.total_excl_tax,
            order.currency,
            basket.id,
            payment_processor.NAME
        )

        # Mark the basket as submitted
        basket.submit()

        return order

    def _assemble_order_data(self, basket, payment_processor):
        """Assemble a dictionary of order metadata using the given basket."""
        order_data = serializers.OrderSerializer(order).data
        # TODO: Provide custom receipt and cancellation pages when generating transaction parameters
        order_data['payment_parameters'] = payment_processor().generate_transaction_parameters(basket)

        return order_data


class FulfillOrderView(FulfillmentMixin, UpdateAPIView):
    permission_classes = (IsAuthenticated, DjangoModelPermissions,)
    lookup_field = 'number'
    queryset = Order.objects.all()
    serializer_class = serializers.OrderSerializer

    def update(self, request, *args, **kwargs):
        order = self.get_object()

        if not order.can_retry_fulfillment:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)

        logger.info('Retrying fulfillment of order [%s]...', order.number)
        order = self._fulfill_order(order)

        if order.can_retry_fulfillment:
            logger.warning('Fulfillment of order [%s] failed!', order.number)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.get_serializer(order)
        return Response(serializer.data)
