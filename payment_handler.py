# payment_handler.py
from loguru import logger

class PaymentHandler:
    """
    Base class for handling payments.
    It should call on_payment_received(amount) when a payment is successfully received,
    and on_error(error) when an error occurs.
    """
    def __init__(self, on_payment_received, on_error):
        self.on_payment_received = on_payment_received
        self.on_error = on_error

    def start(self):
        raise NotImplementedError("start() must be implemented by subclasses.")

    def stop(self):
        raise NotImplementedError("stop() must be implemented by subclasses.")


class MDBPaymentHandler(PaymentHandler):
    """
    Implements payment handling over an MDB interface.
    It reuses the existing coin acceptor logic.
    """
    def __init__(self, iface, on_payment_received, on_error):
        super().__init__(on_payment_received, on_error)
        self.iface = iface

    def _handle_payment(self, value):
        logger.info("MDBPaymentHandler received payment: {}", value)
        self.on_payment_received(value)

    def _handle_error(self, error_code):
        logger.error("MDBPaymentHandler encountered error: {}", error_code)
        self.on_error(error_code)

    def start(self):
        logger.info("Starting MDBPaymentHandler")
        if self.iface is not None:
            self.iface.start()
            # If there's an initialization method to call on the coin acceptor,
            # call it here. Otherwise, log that we're running in real mode.
            if hasattr(self.iface, "onInitCompleted"):
                self.iface.onInitCompleted()
            else:
                logger.info("MDBPaymentHandler: iface has no onInitCompleted method; assuming dummy or alternative mode.")
        else:
            logger.info("MDBPaymentHandler: No iface provided; running in dummy mode.")

    def stop(self):
        logger.info("Stopping MDBPaymentHandler")
        if self.iface is not None:
            try:
                self.iface.stop()
            except AttributeError:
                logger.warning("MDBPaymentHandler: iface has no stop() method.")
        else:
            logger.info("MDBPaymentHandler: No iface provided; running in dummy mode, nothing to stop.")



class OnlinePaymentHandler(PaymentHandler):
    """
    Stub implementation for online payment gateways.
    In a real implementation, this class would integrate with APIs (e.g. Stripe or PayPal).
    """
    def __init__(self, on_payment_received, on_error):
        super().__init__(on_payment_received, on_error)
        # Initialize API clients or other resources here.

    def start(self):
        logger.info("Starting OnlinePaymentHandler")
        # Set up API connections, webhooks, etc.

    def process_online_payment(self, transaction_details):
        logger.info("Processing online payment: {}", transaction_details)
        # Process the transaction details and, on success:
        amount = transaction_details.get("amount", 0)
        self.on_payment_received(amount)
        # In case of error, you might instead call:
        # self.on_error("Online payment error details")

    def stop(self):
        logger.info("Stopping OnlinePaymentHandler")
        # Clean up resources if needed.
