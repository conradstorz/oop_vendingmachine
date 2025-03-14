# -*- coding: utf-8 -*-
import random
from time import sleep
from loguru import logger

class Dispenser:
    """
    Dummy Dispenser module using loguru for logging.
    Simulates vending a product and randomly fails.
    """

    def __init__(self, after_eject=None):
        logger.info("Dummy Dispenser initialized.")

    def init(self):
        logger.info("Dummy Dispenser: Initialization complete.")

    def errors(self):
        # In dummy mode, assume there are no errors.
        return []
    
    def vend(self, product_id):
        """
        Simulate vending a product.
        
        :param product_id: Identifier for the product to vend.
        :return: True if the vend succeeded, False otherwise.
        """
        logger.info("Dummy Dispenser: Attempting to vend product '{}'.", product_id)
        sleep(1)  # Simulate time delay for vend operation.
        if random.random() < 0.8:
            logger.info("Dummy Dispenser: Vend successful for product '{}'.", product_id)
            return True
        else:
            logger.error("Dummy Dispenser: Vend failed for product '{}'.", product_id)
            return False

# Test the dummy dispenser when running this module directly.
if __name__ == "__main__":
    dispenser = Dispenser()
    dispenser.init()
    result = dispenser.vend("test_product")
    if result:
        logger.info("Vend operation completed successfully.")
    else:
        logger.error("Vend operation failed.")
