#!/usr/bin/env python3
'''
##################################################################################
## License
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/gpl-3.0.txt>.
#
##################################################################################
'''
import logging
import signal
import random
import configargparse
from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
import pyhap.loader as loader
from pyhap import camera
from pyhap.const import *
from pyhap.service import Service
from pyhap.characteristic import *

logging.basicConfig(level=logging.INFO, format="[%(module)s] %(message)s")

VERSION = '23/02/2023'
AUTHOR = 'SW Engineer Garzola Marco'


NameDev   = 'HAA Simulator'
Manufacturer =  "José A. Jiménez Campos"
SerialNumber =  "112233-1"
Model =         "RavenSystem HAA Peregrine"
FirmwareVersion =     "11.9"

HAA_CUSTOM_SERVICE = "F0000100-0218-2017-81BF-AF2B7C833922"
HAA_CUSTOM_CONFIG_CHAR = "F0000101-0218-2017-81BF-AF2B7C833922"

CHAR_PROPS = {
    PROP_FORMAT: HAP_FORMAT_STRING,
    PROP_PERMISSIONS: [HAP_PERMISSION_READ,HAP_PERMISSION_HIDDEN,HAP_PERMISSION_WRITE]
}


parser = configargparse.ArgParser(default_config_files=[''])
parser.add('-v', action='version', version=VERSION + "\n" + AUTHOR)
parser.add('-f', '--fw', required=True, type=str, default=FirmwareVersion, help='FW Version of the Dev Simulator')


class TemperatureSensor(Accessory):
    """Fake Temperature sensor, measuring every 3 seconds."""

    category = CATEGORY_SENSOR

    def __init__(self, version = FirmwareVersion, *args, **kwargs ):
        super().__init__(*args, **kwargs)

        logger.info("Create Fake HAA device with version {}".format(version))
        serv_temp = self.add_preload_service('TemperatureSensor')
        self.char_temp = serv_temp.configure_char('CurrentTemperature')
        self.set_info_service(firmware_revision=version,      
                                manufacturer=Manufacturer,
                                serial_number=SerialNumber,model=Model)
        service = Service(HAA_CUSTOM_SERVICE,"Setup Service", unique_id="my_service_unique_id")
        c = Characteristic(HAA_CUSTOM_CONFIG_CHAR, HAA_CUSTOM_CONFIG_CHAR, CHAR_PROPS)
        service.characteristics = [c]
        c.setter_callback = self.on_custom_service_char
        self.add_service(service)


    @Accessory.run_at_interval(3)
    async def run(self):
        self.char_temp.set_value(random.randint(18, 26))

    def on_custom_service_char(self,value):
        print(value)
 
def get_accessory(driver,fw = FirmwareVersion):
    """Call this method to get a standalone Accessory."""
    return TemperatureSensor(fw,driver,NameDev)


if __name__ == '__main__':

    config = parser.parse_args()

    # Start the accessory on port 51826
    driver = AccessoryDriver(port=51826)

    # Change `get_accessory` to `get_bridge` if you want to run a Bridge.
    haa = get_accessory(driver,config.fw)
    driver.add_accessory(accessory=haa)

    # We want SIGTERM (terminate) to be handled by the driver itself,
    # so that it can gracefully stop the accessory, server and advertising.
    signal.signal(signal.SIGTERM, driver.signal_handler)

    # Start it!
    driver.start()