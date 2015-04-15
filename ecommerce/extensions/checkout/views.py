# noinspection PyUnresolvedReferences
from oscar.apps.checkout.views import *  # noqa
from ecommerce.extensions.payment.processors import Cybersource


class PaymentDetailsView(PaymentDetailsView):
    def get_context_data(self, **kwargs):
        context = super(PaymentDetailsView, self).get_context_data(**kwargs)

        if self.preview:
            processor = Cybersource()
            context.update({
                'payment_endpoint': processor.endpoint,
                'payment_form_parameters': processor.get_transaction_parameters(self.request.basket)
            })

        return context
