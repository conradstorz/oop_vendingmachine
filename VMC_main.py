#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VMC_main.py
Main entry point for the vending machine control system.

This version abstracts away Raspberry Pi-specific hardware details so that
the code can be tested on non-Pi platforms.
"""

from loguru import logger
import sys
from time import sleep
import os
import signal

# Loguru configuration: Create the LOGS directory and rotate logs at midnight.
os.makedirs("LOGS", exist_ok=True)
logger.remove()
logger.add("LOGS/vending_machine_{time:YYYY-MM-DD}.log",
           rotation="00:00",
           level="DEBUG",
           retention="7 days",
           backtrace=True,
           diagnose=True)

import sound
from one_off_file_storage import OneOffFileStorage as PersistentStorage
import watchdog
from configuration import config as from_config

# Hardware abstraction: these modules provide dummy implementations on non-Pi platforms.
from i2c_relay import I2cRelay
from button import Button
from dispenser import Dispenser
from cashier import Cashier
from payment_handler import MDBPaymentHandler, OnlinePaymentHandler
from custom_state_machine import CustomStateMachine

class Machine:
    # Define FSM states with timeouts and callbacks.
    states = [
        {"name": "oos"},  # Out Of Service
        {"name": "idle",
         "timeout": from_config.getint("machine", "idle_timeout", fallback=30),
         "on_timeout": "on_timeout_idle"},
        {"name": "entertain",
         "timeout": from_config.getint("machine", "entertain_timeout", fallback=15),
         "on_timeout": "on_timeout_entertain"},
        {"name": "refund",
         "timeout": from_config.getint("machine", "refund_timeout", fallback=10),
         "on_timeout": "on_timeout_refund"},
        {"name": "proceed_to_vend"},
    ]

    # Define transitions.
    transitions = [
        {"trigger": "to_idle", "source": ["oos", "entertain", "refund", "proceed_to_vend"], "dest": "idle"},
        {"trigger": "entertain", "source": "idle", "dest": "entertain"},
        {"trigger": "refund", "source": "idle", "dest": "refund"},
        {"trigger": "vend_item_now", "source": "idle", "dest": "proceed_to_vend"},
        {"trigger": "recover", "source": "oos", "dest": "idle"},
        {"trigger": "turn_off", "source": ["idle", "entertain", "refund"], "dest": "oos"},
    ]

    def __init__(self, kwargs=None):
        logger.info("Initializing Vending Machine...")

        # Create the state machine controlling the machine's states.
        self.state_machine = CustomStateMachine(
            model=self,
            states=Machine.states,
            transitions=Machine.transitions,
            send_event=True,
            initial="oos",
        )

        # Set up persistent storage for saving machine state and statistics.
        self.storage = PersistentStorage(from_config.get("persistence", "directory"))
        self.deposit = self.storage.get_int("deposit", fallback=0)
        self.stats = {
            "cash_box": self.storage.get_int("cash_box", fallback=0),
            "items_sold": self.storage.get_int("items_sold", fallback=0),
        }

        # Load the item price from the configuration.
        self.item_price = from_config.getint("item", "item_price")

        # Initialize hardware abstractions.
        self.front_panel = I2cRelay(**dict(from_config.items("front_panel")))
        self.button = Button(
            gpio_pin=from_config.getint("button", "gpio_pin"),
            on_press=self.on_button_press
        )
        self.button_led = I2cRelay(**dict(from_config.items("button_led")))
        self.dispenser = Dispenser(after_eject=self.on_item_ejected)
        self.cashier = Cashier()

        # Set up payment handler.
        self.payment_handler = MDBPaymentHandler(
            iface=None,  # In dummy mode, iface may be None.
            on_payment_received=self.on_coin_insert,
            on_error=self.on_ca_error,
        )
        self.payment_handler.start()
        sleep(2)  # Allow time for hardware to stabilize.

        # Start the watchdog to monitor machine errors.
        self.watchdog = watchdog.Watchdog(
            error_probe_cb=self.has_errors,
            on_error_cb=self.on_error,
            on_recover_cb=self.on_recover,
        )
        self.watchdog.start()

        # Begin operation by setting the machine to idle.
        self.trigger("to_idle")
        logger.info("Vending Machine initialized: state='{}', deposit={}", self.state, self.deposit)

    @property
    def state(self):
        return self.state_machine.state

    def trigger(self, trigger_name):
        logger.debug("Machine.trigger called with trigger '{}'", trigger_name)
        self.state_machine.trigger(trigger_name)
        logger.debug("Machine state after trigger: '{}'", self.state)

    def try_trigger(self, trigger_name):
        valid_triggers = self.state_machine.get_triggers(self.state)
        logger.debug("Available triggers from state '{}': {}", self.state, valid_triggers)
        if trigger_name in valid_triggers:
            logger.debug("Attempting trigger '{}'", trigger_name)
            try:
                self.trigger(trigger_name)
            except Exception as e:
                logger.error("Failed to trigger '{}': {}", trigger_name, e)
        else:
            logger.warning("Trigger '{}' not valid from state '{}'", trigger_name, self.state)

    def increase_deposit(self, value):
        logger.debug("Increasing deposit by {}", value)
        self.deposit += value
        self.storage.set_int("deposit", self.deposit)
        logger.info("Current deposit after increase: {}", self.deposit)

    def decrease_deposit(self, value):
        logger.debug("Decreasing deposit by {}", value)
        self.deposit -= value
        self.storage.set_int("deposit", self.deposit)
        logger.info("Current deposit after decrease: {}", self.deposit)

    def refund_deposit(self):
        logger.info("Refunding deposit: {}.", self.deposit)
        # Add refund logic here. For dummy mode, we simply reset the deposit.
        self.deposit = 0
        self.storage.set_int("deposit", self.deposit)

    def has_deposit(self, *event):
        result = self.deposit >= self.item_price
        logger.debug("Checking deposit condition: deposit={}, item_price={}, result={}",
                     self.deposit, self.item_price, result)
        return result

    def has_errors(self):
        # For dummy mode, assume dispenser.errors() returns an empty list.
        errors = self.dispenser.errors() if hasattr(self.dispenser, "errors") else []
        error_count = len(errors)
        # logger.debug("Checking dispenser errors: {} errors found", error_count)
        return error_count > 0

    # State machine callbacks:
    def on_timeout_idle(self, _event):
        # In idle, if no customer interaction occurs for a set time:
        if self.deposit == 0:
            logger.info("Idle timeout with no deposit. Transitioning to entertain mode.")
            self.trigger("entertain")
        else:
            logger.info("Idle timeout with deposit present. Transitioning to refund mode.")
            self.trigger("refund")

    def on_timeout_entertain(self, _event):
        # After advertisement period ends, return to idle.
        logger.info("Entertainment period ended. Returning to idle.")
        self.trigger("to_idle")

    def on_timeout_refund(self, _event):
        # Process refund if idle too long with deposit.
        if self.deposit > 0:
            logger.info("Refund period timeout: processing refund for deposit of {}.", self.deposit)
            self.refund_deposit()
        else:
            logger.info("Refund timeout: no deposit found.")
        self.trigger("to_idle")

    def on_enter_proceed_to_vend(self, _event):
        logger.info("Entering 'proceed_to_vend' state. Attempting to vend item...")
        # Call the dispenser to vend the product. You can choose a product_id or get it from elsewhere.
        result = self.dispenser.vend("product_id")
        if result:
            logger.info("Item vended successfully.")
            self.on_item_ejected()  # This updates deposit, stats, and creates a receipt.
        else:
            logger.error("Vend failed. Transitioning to refund state.")
            self.trigger("refund")
        # After vend attempt, return the machine to idle.
        self.trigger("to_idle")

    def on_button_press(self, _event):
        logger.info("Button pressed by customer.")
        # A button press indicates customer interaction: cancel any entertain/refund process.
        self.trigger("to_idle")
        # You might also trigger vend_item_now if the deposit is sufficient.
        if self.deposit >= self.item_price:
            self.trigger("vend_item_now")

    def on_coin_insert(self, value):
        logger.info("Payment received: {}", value)
        self.increase_deposit(value)
        self.stats["cash_box"] += value
        self.storage.set_int("cash_box", self.stats["cash_box"])
        logger.debug("Updated cash box: {}", self.stats["cash_box"])
        # Remain in idle; the idle timeout will handle transitioning to refund if needed.

    def on_ca_error(self, code):
        logger.warning("Payment handler error: {}", code)

    def on_item_ejected(self):
        logger.info("Item successfully dispensed.")
        self.cashier.create_receipt(self.item_price)
        self.decrease_deposit(self.item_price)
        self.stats["items_sold"] += 1
        self.storage.set_int("items_sold", self.stats["items_sold"])
        logger.debug("Updated items sold: {}", self.stats["items_sold"])

    def on_error(self):
        logger.warning("Error detected by watchdog, turning machine off.")
        self.try_trigger("turn_off")

    def on_recover(self):
        logger.info("Recovery detected by watchdog, returning machine to idle.")
        self.try_trigger("to_idle")

    def sig_handler(self, sig, frame):
        logger.warning("Interrupt signal received; shutting down machine.")
        self.watchdog.stop()
        self.watchdog.join()
        self.payment_handler.stop()
        self.front_panel.off()
        self.button.cleanup()
        self.button_led.cleanup()
        sys.exit(0)

if __name__ == "__main__":
    machine = Machine()

    # Set up signal handlers for graceful shutdown.
    signal.signal(signal.SIGINT, machine.sig_handler)
    signal.signal(signal.SIGTERM, machine.sig_handler)

    try:
        while True:
            sleep(.001)
    except KeyboardInterrupt:
        machine.sig_handler(None, None)
