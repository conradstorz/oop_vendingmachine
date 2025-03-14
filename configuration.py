# -*- coding: utf-8 -*-

import os
from configparser import ConfigParser

# Construct the full path to the config file in the current working directory
configfile = os.path.join(os.getcwd(), "VENDINGMACHINE_CONFIG_FILE")

if not os.path.exists(configfile):
    raise FileNotFoundError(f"Configuration file not found: {configfile}")

config = ConfigParser()
config.read(configfile, encoding="utf-8")
