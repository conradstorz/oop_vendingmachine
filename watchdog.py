import threading
from time import sleep
from loguru import logger

class Watchdog(threading.Thread):
    """
    Monitors `error_probe_cb` callback result every `interval` seconds.
    If the result changes to True, runs on_error_cb; otherwise runs on_recover_cb.
    """
    def __init__(self, error_probe_cb=None, on_error_cb=None, on_recover_cb=None, interval=3):
        super().__init__(name="Watchdog")
        self.callback_for = {True: on_error_cb, False: on_recover_cb}
        self.error_probe_cb = error_probe_cb
        self.interval = interval
        self.healthy = None
        self._stop_event = threading.Event()
        logger.debug("Initialized Watchdog with interval {} seconds", self.interval)

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info("Watchdog started.")
        last = self.error_probe_cb()
        logger.info("Initial error state: {}", last)
        while not self._stop_event.is_set():
            # Wait for the interval, but exit early if stop is requested.
            if self._stop_event.wait(self.interval):
                break
            state = self.error_probe_cb()
            logger.debug("Watchdog check: current error state: {}", state)
            if last != state:
                logger.info("Error state changed from {} to {}. Executing callback.", last, state)
                callback = self.callback_for.get(state)
                if callback:
                    callback()
                last = state
        logger.info("Watchdog stopped.")
