# -*- coding: utf-8 -*-

try:
    import smbus
except ImportError:
    # Define a dummy SMBus for environments without the smbus module.
    class DummySMBus:
        def __init__(self, bus_id):
            self.bus_id = bus_id
            print(f"DummySMBus: Initialized dummy bus {bus_id}")
        def write_byte_data(self, addr, reg, value):
            print(f"DummySMBus: Pretend writing value {value} to device {addr}, register {reg}")
        def read_byte_data(self, addr, reg):
            print(f"DummySMBus: Pretend reading from device {addr}, register {reg}")
            # Return OFF by default, you can adjust this behavior if needed.
            return 0x00

    # Create a dummy smbus module with an SMBus attribute.
    class DummySmbusModule:
        SMBus = DummySMBus
    smbus = DummySmbusModule()

ON = 0xFF
OFF = 0x00

class I2cRelay:
    def __init__(self, i2c_bus_id, i2c_device_addr, relay_number):
        self.bus = smbus.SMBus(int(i2c_bus_id))
        self.i2c_device_addr = int(i2c_device_addr)
        self.relay_number = int(relay_number)

    def cleanup(self):
        self.off()

    def on(self):
        self.bus.write_byte_data(self.i2c_device_addr, self.relay_number, ON)

    def off(self):
        self.bus.write_byte_data(self.i2c_device_addr, self.relay_number, OFF)

    def state(self):
        return self.bus.read_byte_data(self.i2c_device_addr, self.relay_number)

    def is_on(self):
        return self.state() == ON

    def is_off(self):
        return self.state() == OFF
