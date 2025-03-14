import threading
from time import sleep
from loguru import logger

class Watchdog(threading.Thread):
    """
    Monitors `error_probe_cb` callback result every `interval` seconds.
    If the result changes to True, runs on_error_cb; otherwise runs on_recover_cb.
    """
    _loop = True

    def __init__(self, error_probe_cb=None, on_error_cb=None, on_recover_cb=None, interval=3):
        threading.Thread.__init__(self)
        self.name = "Watchdog"
        self.callback_for = {True: on_error_cb, False: on_recover_cb}
        self.error_probe_cb = error_probe_cb
        self.interval = interval
        self.healthy = None
        logger.debug("Initialized Watchdog with interval {} seconds", self.interval)

    @classmethod
    def stop(cls):
        cls._loop = False

    def run(self):
        logger.info("Watchdog started.")
        last = self.error_probe_cb()
        logger.info("Initial error state: {}", last)
        while self.__class__._loop:
            sleep(self.interval)
            state = self.error_probe_cb()
            logger.debug("Watchdog check: current error state: {}", state)
            if last == state:
                continue
            logger.info("Error state changed from {} to {}. Executing callback.", last, state)
            self.callback_for[state]()
            last = state
        logger.info("Watchdog stopped.")
