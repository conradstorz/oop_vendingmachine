# -*- coding: utf-8 -*-
from loguru import logger
import sys
from time import sleep
import os

# Loguru configuration
os.makedirs("LOGS", exist_ok=True)
logger.remove()
logger.add("LOGS/vending_machine_{time:YYYY-MM-DD}.log",
           rotation="00:00",
           level="DEBUG",
           retention="7 days",
           backtrace=True,
           diagnose=True)

import sound
import one_off_file_storage as PersistentStorage
import watchdog
import config

# Updated imports for missing classes
from coin_acceptor import SerialInterface, MyCoinAcceptor
from i2c_relay import I2cRelay
from button import Button
from dispenser import Dispenser
from cashier import Cashier

logger.info("Setting up Machine...")

class Machine:
    states = [
        {"name": "oos"},
        {"name": "idling"},
        {"name": "entertaining",
         "timeout": config.getint("button", "press_timeout", fallback=10),
         "on_timeout": "on_timeout_entertaining"},
        {"name": "ejecting"},
    ]

    transitions = [
        {"trigger": "idle", "source": ["oos", "ejecting"], "dest": "idling"},
        {"trigger": "entertain", "source": "idling", "dest": "entertaining", "conditions": "has_deposit"},
        {"trigger": "eject_item", "source": "entertaining", "dest": "ejecting", "conditions": "has_deposit"},
        {"trigger": "recover", "source": "oos", "dest": "idling"},
        {"trigger": "turn_off", "source": ["idling", "entertaining"], "dest": "oos"},
    ]

    def __init__(self, kwargs=None):
        logger.info("Initializing Machine...")
        self.sm = CustomStateMachine(
            model=self,
            states=Machine.states,
            transitions=Machine.transitions,
            send_event=True,
            initial="oos",
        )
        self.p9e = PersistentStorage(config.get("persistence", "directory"))
        self.deposit = self.p9e.get_int("deposit", fallback=0)
        self.stats = {
            "cash_box": self.p9e.get_int("cash_box", fallback=0),
            "items_sold": self.p9e.get_int("items_sold", fallback=0),
        }
        self.item_price = config.getint("item", "item_price")
        self.front_panel = I2cRelay(**dict(config.items("front_panel")))
        self.button = Button(
            gpio_pin=config.getint("button", "gpio_pin"), on_press=self.on_button_press
        )
        self.button_led = I2cRelay(**dict(config.items("button_led")))
        self.dispenser = Dispenser(after_eject=self.on_item_ejected)
        self.cashier = Cashier()
        self.coin_acceptor_interface = SerialInterface(
            config.get("coin_acceptor", "interface")
        )
        self.coin_acceptor = MyCoinAcceptor(
            self.coin_acceptor_interface,
            insert_cb=self.on_coin_insert,
            error_cb=self.on_ca_error,
        )
        self.coin_acceptor_interface.start()
        logger.info("Coin acceptor interface started, waiting for stabilization...")
        sleep(2)
        self.watchdog = watchdog.Watchdog(
            error_probe_cb=self.has_errors,
            on_error_cb=self.on_error,
            on_recover_cb=self.on_recover,
        )
        self.watchdog.start()
        logger.info("Watchdog thread started.")
        self.trigger("idle")
        logger.info("Machine initialized with state: '{}', deposit: {}", self.state, self.deposit)

    @property
    def state(self):
        return self.sm.state

    def trigger(self, trigger_name):
        logger.debug("Machine.trigger called with trigger '{}'", trigger_name)
        self.sm.trigger(trigger_name)
        logger.debug("Machine state after trigger: '{}'", self.state)

    def try_trigger(self, trigger_name):
        valid_triggers = self.sm.get_triggers(self.state)
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
        self.p9e.set_int("deposit", self.deposit)
        logger.info("Current deposit after increase: {}", self.deposit)

    def decrease_deposit(self, value):
        logger.debug("Decreasing deposit by {}", value)
        self.deposit -= value
        self.p9e.set_int("deposit", self.deposit)
        logger.info("Current deposit after decrease: {}", self.deposit)

    def has_deposit(self, *event):
        result = self.deposit >= self.item_price
        logger.debug("Checking deposit condition: deposit={}, item_price={}, result={}",
                     self.deposit, self.item_price, result)
        return result

    def has_errors(self):
        errors = self.dispenser.errors()
        error_count = len(errors)
        logger.debug("Checking dispenser errors: {} errors found", error_count)
        return error_count > 0

    def on_enter_idling(self, _event):
        logger.info("Entering 'idling' state")
        self.trigger("entertain")

    def on_exit_idling(self, _event):
        logger.info("Exiting 'idling' state")

    def on_enter_entertaining(self, _event):
        logger.info("Entering 'entertaining' state")
        self.button_led.on()

    def on_exit_entertaining(self, _event):
        logger.info("Exiting 'entertaining' state")
        self.button_led.off()

    def on_timeout_entertaining(self, _event):
        logger.info("Timeout in 'entertaining' state, triggering eject")
        self.trigger("eject_item")

    def on_enter_ejecting(self, _event):
        logger.info("Entering 'ejecting' state")
        self.dispenser.eject()
        self.try_trigger("idle")

    def on_exit_ejecting(self, _event):
        logger.info("Exiting 'ejecting' state")

    def on_enter_oos(self, _event):
        logger.info("Entering 'oos' state")
        self.front_panel.off()
        self.coin_acceptor.setInhibitOn()

    def on_exit_oos(self, _event):
        logger.info("Exiting 'oos' state")
        self.front_panel.on()
        self.button.enable()
        self.coin_acceptor.setInhibitOff()

    def on_button_press(self, _event):
        logger.info("Button pressed")
        self.try_trigger("eject_item")

    def on_coin_insert(self, value):
        logger.info("Coin inserted: {}", value)
        self.increase_deposit(value)
        self.stats["cash_box"] += value
        self.p9e.set_int("cash_box", self.stats["cash_box"])
        logger.debug("Updated cash box: {}", self.stats["cash_box"])
        self.try_trigger("entertain")

    def on_ca_error(self, code):
        logger.warning("Coin acceptor error: {}", code)

    def on_item_ejected(self):
        logger.info("Item ejected")
        self.cashier.create_receipt(self.item_price)
        self.decrease_deposit(self.item_price)
        self.stats["items_sold"] += 1
        self.p9e.set_int("items_sold", self.stats["items_sold"])
        logger.debug("Updated items sold: {}", self.stats["items_sold"])

    def on_error(self):
        logger.warning("Error detected by watchdog, turning machine off")
        self.try_trigger("turn_off")

    def on_recover(self):
        logger.info("Recovery detected by watchdog, recovering machine")
        self.try_trigger("recover")

    def sig_handler(self, sig, frame):
        logger.warning("Interrupt signal received")
        self.watchdog.stop()
        self.watchdog.join()
        self.coin_acceptor.stop()
        self.front_panel.off()
        self.button.cleanup()
        self.button_led.cleanup()
        sys.exit(0)
