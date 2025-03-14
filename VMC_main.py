# -*- coding: utf-8 -*-
# Author: Vladimir Gorodulin (modified)

import logging
import sys
from time import sleep
from custom_state_machine import CustomStateMachine  # Updated import for the state machine
import sound
import one_off_file_storage as PersistentStorage
import watchdog  # Assumes watchdog provides a Watchdog class
import config

# Updated imports for missing classes
from coin_acceptor import SerialInterface, MyCoinAcceptor
from i2c_relay import I2cRelay
from button import Button
from dispenser import Dispenser
from cashier import Cashier

logger = logging.getLogger(__name__)
logging.getLogger('transitions').setLevel(logging.INFO)

class Machine():
    states = [
        {'name': 'oos'},  # 'oos' stands for 'out of service'
        {'name': 'idling'},
        {'name': 'entertaining', 'timeout': config.getint('button', 'press_timeout', fallback=10), 'on_timeout': 'on_timeout_entertaining'},
        {'name': 'ejecting'}
    ]

    transitions = [
        {'trigger': 'idle', 'source': ['oos', 'ejecting'], 'dest': 'idling'},
        {'trigger': 'entertain', 'source': 'idling', 'dest': 'entertaining', 'conditions': 'has_deposit'},
        {'trigger': 'eject_item', 'source': 'entertaining', 'dest': 'ejecting', 'conditions': 'has_deposit'},
        {'trigger': 'recover', 'source': 'oos', 'dest': 'idling'},
        {'trigger': 'turn_off', 'source': ['idling', 'entertaining'], 'dest': 'oos'}
    ]
    
    def __init__(self, kwargs=None):
        # Initialize the state machine with this instance as the model
        self.sm = CustomStateMachine(model=self, states=Machine.states, transitions=Machine.transitions, send_event=True, initial='oos')
        self.p9e = PersistentStorage(config.get('persistence', 'directory'))  # 'p9e' stands for 'persistence'
        self.deposit = self.p9e.get_int('deposit', fallback=0)
        self.stats = {
            'cash_box': self.p9e.get_int('cash_box', fallback=0),
            'items_sold':  self.p9e.get_int('items_sold', fallback=0),
        }
        self.item_price = config.getint('item', 'item_price')
        self.front_panel = I2cRelay(**dict(config.items('front_panel')))
        self.button = Button(gpio_pin=config.getint('button', 'gpio_pin'), on_press=self.on_button_press)
        # Using I2cRelay for the button LED as well
        self.button_led = I2cRelay(**dict(config.items('button_led')))
        self.dispenser = Dispenser(after_eject=self.on_item_ejected)
        self.cashier = Cashier()
        self.coin_acceptor_interface = SerialInterface(config.get('coin_acceptor', 'interface'))
        self.coin_acceptor = MyCoinAcceptor(self.coin_acceptor_interface, insert_cb=self.on_coin_insert, error_cb=self.on_ca_error)
        self.coin_acceptor_interface.start()
        sleep(2)  # See https://github.com/pyserial/pyserial/issues/86#issuecomment-515116454
        self.watchdog = watchdog.Watchdog(error_probe_cb=self.has_errors, on_error_cb=self.on_error, on_recover_cb=self.on_recover)
        self.watchdog.start()
        self.trigger('idle')

    @property
    def state(self):
        # Expose the current state from the state machine
        return self.sm.state

    def trigger(self, trigger_name):
        """Proxy trigger calls to the state machine."""
        self.sm.trigger(trigger_name)

    def try_trigger(self, trigger_name):
        """Run trigger only if it is valid from the current state."""
        valid_triggers = self.sm.get_triggers(self.state)
        if trigger_name in valid_triggers:
            self.trigger(trigger_name)

    def increase_deposit(self, value):
        logger.debug("call increase_deposit({})".format(value))
        self.deposit += value
        self.p9e.set_int('deposit', self.deposit)
        logger.debug("Current deposit: {}".format(self.deposit))

    def decrease_deposit(self, value):
        logger.debug("call decrease_deposit({})".format(value))
        self.deposit -= value
        self.p9e.set_int('deposit', self.deposit)
        logger.debug("Current deposit: {}".format(self.deposit))

    def has_deposit(self, *event):
        return self.deposit >= self.item_price

    def has_errors(self):
        # Assumes dispenser.errors() returns an iterable of errors
        return len(self.dispenser.errors()) > 0

    # State machine callbacks:
    def on_enter_idling(self, _event):
        logger.debug("call on_enter_idling()")
        self.trigger('entertain')

    def on_exit_idling(self, _event):
        logger.debug("call on_exit_idling()")

    def on_enter_entertaining(self, _event):
        logger.debug("call on_enter_entertaining()")
        self.button_led.on()
        # Optionally enable button or play music:
        # self.button.enable()
        # sound.play_random(sound.MUSIC)

    def on_exit_entertaining(self, _event):
        logger.debug("call on_exit_entertaining()")
        self.button_led.off()
        # Optionally disable button or stop sound:
        # self.button.disable()
        # sound.stop()

    def on_timeout_entertaining(self, _event):
        logger.debug("call on_timeout_entertaining()")
        self.trigger('eject_item')

    def on_enter_ejecting(self, _event):
        logger.debug("call on_enter_ejecting()")
        # sound.play_random(sound.BUTTON_PRESS)
        self.dispenser.eject()
        self.try_trigger('idle')

    def on_exit_ejecting(self, _event):
        logger.debug("call on_exit_ejecting()")
        # sound.stop()

    def on_enter_oos(self, _event):
        logger.debug("call on_enter_oos()")
        self.front_panel.off()
        self.coin_acceptor.setInhibitOn()

    def on_exit_oos(self, _event):
        logger.debug("call on_exit_oos()")
        self.front_panel.on()
        self.button.enable()
        self.coin_acceptor.setInhibitOff()

    # Other callbacks:
    def on_button_press(self, _event):
        logger.debug("call on_button_press()")
        self.try_trigger('eject_item')

    def on_coin_insert(self, value):
        logger.debug("call on_coin_insert({})".format(value))
        self.increase_deposit(value)
        self.stats['cash_box'] += value
        self.p9e.set_int('cash_box', self.stats['cash_box'])
        # sound.play_random(sound.COIN_INSERT)
        self.try_trigger('entertain')

    def on_ca_error(self, code):
        logger.warning("call on_ca_error({})".format(code))

    def on_item_ejected(self):
        self.cashier.create_receipt(self.item_price)
        self.decrease_deposit(self.item_price)
        self.stats['items_sold'] += 1
        self.p9e.set_int('items_sold', self.stats['items_sold'])

    def on_error(self):
        logger.debug("call on_error()")
        self.try_trigger('turn_off')

    def on_recover(self):
        logger.debug("call on_recover()")
        self.try_trigger('recover')

    def sig_handler(self, sig, frame):
        logger.warning("Interrupt signal received")
        self.watchdog.stop()
        self.watchdog.join()
        self.coin_acceptor.stop()
        self.front_panel.off()
        self.button.cleanup()
        self.button_led.cleanup()
        sys.exit(0)
