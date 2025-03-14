# -*- coding: utf-8 -*-

try:
    import RPi.GPIO as GPIO
except ImportError:
    # Dummy GPIO implementation for non-Raspberry Pi environments.
    class DummyGPIO:
        BCM = "BCM"
        RISING = "RISING"
        FALLING = "FALLING"
        BOTH = "BOTH"
        PUD_DOWN = "PUD_DOWN"
        _mode = None

        @classmethod
        def getmode(cls):
            return cls._mode

        @classmethod
        def setmode(cls, mode):
            cls._mode = mode
            print(f"DummyGPIO: setmode({mode})")

        @classmethod
        def setup(cls, channel, direction, **kwargs):
            print(f"DummyGPIO: setup(channel={channel}, direction={direction}, kwargs={kwargs})")

        @classmethod
        def add_event_detect(cls, channel, edge, callback, bouncetime=200):
            print(f"DummyGPIO: add_event_detect(channel={channel}, edge={edge}, bouncetime={bouncetime})")
            # Optionally, you could simulate an event after a delay if needed.

        @classmethod
        def remove_event_detect(cls, channel):
            print(f"DummyGPIO: remove_event_detect(channel={channel})")

        @classmethod
        def cleanup(cls, channel=None):
            print(f"DummyGPIO: cleanup(channel={channel})")

    GPIO = DummyGPIO

class Button:
    def __init__(self, gpio_pin, on_press):
        self.channel = int(gpio_pin)
        self.callback = on_press
        if not GPIO.getmode():
            GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.channel, GPIO.IN)  # Optionally, add pull_up_down=GPIO.PUD_DOWN if needed.
        self._enabled = False

    def enable(self):
        if not self._enabled:
            # You can choose the appropriate event detection type.
            GPIO.add_event_detect(
                self.channel, GPIO.RISING, callback=self.callback, bouncetime=200
            )
            self._enabled = True

    def disable(self):
        if self._enabled:
            GPIO.remove_event_detect(self.channel)
            self._enabled = False

    def cleanup(self):
        GPIO.cleanup(self.channel)
