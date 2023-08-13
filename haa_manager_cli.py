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

import argparse
import requests
import sys,socket,os
import logging
import signal as unixsignal
from logging.handlers import RotatingFileHandler
import configargparse
from homekit.controller import Controller
from homekit.model.characteristics import CharacteristicsTypes
from homekit.model.services import ServicesTypes
import urllib.request
from scapy.all import ARP, Ether, srp

VERSION = '23/02/2023'
AUTHOR = 'SW Engineer Garzola Marco'

HAA_MANUFACTURER = "RavenSystem HAA"
SERVICE_INFO_TYPE = "0000003E-0000-1000-8000-0026BB765291"
SERVICE_INFO_CHAR_NAME = "00000023-0000-1000-8000-0026BB765291"
SERVICE_INFO_CHAR_MANUF = "00000021-0000-1000-8000-0026BB765291"
SERVICE_INFO_CHAR_FW_REV = "00000052-0000-1000-8000-0026BB765291"

CUSTOM_HAA_COMMAND = "#HAA@trcmd"

HAA_CUSTOM_SERVICE = "F0000100-0218-2017-81BF-AF2B7C833922"
HAA_CUSTOM_CONFIG_CHAR = "F0000101-0218-2017-81BF-AF2B7C833922"
SETUP_PORT = 4567


ALL_DEVICES_WILDCARD = "*"

FILELOGSIZE = 1024 * 1024 * 10  # 10 mb max

############### CUSTOM COMMANDS ##################
#if you add something keep the order..
CustomCommands = {
    "12.8.0":  "ic",
    "12.3.0":  "zc",
    "12.0.0":  "io",
    "11.9.0" : "rgb",
    "11.8.0" : "cmy"
}
###################################################



parser = configargparse.ArgParser(default_config_files=[''])
# parser.add('-c', '--my-config', required=False, is_config_file=True, help='config file path')
parser.add("-l", "--log", nargs=1, metavar=("log File"), default=False,
           help=" path file to save log")  # this option can be set in a config file because it starts with '--'
parser.add('-v', action='version', version=VERSION + "\n" + AUTHOR)
parser.add('-d', '--debug', action='store_true', default=False, help='debug mode')
parser.add('-t', '--timeout', required=False, type=int, default=10, help='Number of seconds to wait')
parser.add('-f', action='store', required=True, dest='file', help='File with the pairing data')
parser.add('-n', action='store', required=False, dest='name', help='name of device found online,shown on scan. wildcard "*" means all')
parser.add_argument("-e", "--exec", required=True, type=str,
                    choices=['update', 'reboot', 'setup', 'wifi', 'dump', 'scan','version'],
                    help="type of action to execute")


# versiontuple("2.3.1") > versiontuple("10.1.1") -> False
def versiontuple(v):
    return tuple(map(int, (v.split("."))))

# Method to compare two versions.
# Return 1 if v2 is smaller,
# -1 if v1 is smaller,
# 0 if equal
# Driver program to check above comparison function
# version1 = "1.0.3"
# version2 = "1.0.7"
# ans = versionCompare(version1, version2)
#    if ans < 0:
#        print (version1 + " is smaller")
#    else if ans > 0:
#        print (version2 + " is smaller")
#   else:
#        print ("Both versions are equal")

def versionCompare(v1, v2):

    if versiontuple(v2) <  versiontuple(v1) :
       return 1

    if  versiontuple(v1) <  versiontuple(v2) :
       return -1

    if  versiontuple(v1)  ==  versiontuple(v2) :
       return 0


class HAADevice:
    def __init__(self, zcinfo, data, pairing):
        self.pairing = pairing
        self.info = zcinfo
        self.data = data
        self.fwversion = self._getfwversion()
        self.name = self._getname()
        self.manufacturer = self._getManufacturer()
        self.setupChar = self._getCustomSetupService()
        if self.manufacturer != self._getManufacturer():
            sys.exit(-1)

    def _getCustomSetupService(self):
        for accessory in self.data:
            aid = accessory['aid']
            for service in accessory['services']:
                s_type = service['type']
                s_iid = service['iid']
                if s_type == HAA_CUSTOM_SERVICE:
                    for characteristic in service['characteristics']:
                        if characteristic.get('type') == HAA_CUSTOM_CONFIG_CHAR:
                            value = characteristic.get('value', '')
                            # 'aid': 1, 'iid': 65011,
                            return [int(characteristic.get('aid')), int(characteristic.get('iid'))]
        return None

    def _getfwversion(self):
        for accessory in self.data:
            aid = accessory['aid']
            for service in accessory['services']:
                s_type = service['type']
                s_iid = service['iid']
                if s_type == SERVICE_INFO_TYPE:
                    for characteristic in service['characteristics']:
                        if characteristic.get('type') == SERVICE_INFO_CHAR_FW_REV:
                            value = characteristic.get('value', '')
                            return value
        return None

    def _getManufacturer(self):
        for accessory in self.data:
            aid = accessory['aid']
            for service in accessory['services']:
                s_type = service['type']
                s_iid = service['iid']
                if s_type == SERVICE_INFO_TYPE:
                    for characteristic in service['characteristics']:
                        if characteristic.get('type') == SERVICE_INFO_CHAR_MANUF:
                            value = characteristic.get('value', '')
                            return value
        return None

    def _getname(self):
        for accessory in self.data:
            aid = accessory['aid']
            for service in accessory['services']:
                s_type = service['type']
                s_iid = service['iid']
                if s_type == SERVICE_INFO_TYPE:
                    for characteristic in service['characteristics']:
                        if characteristic.get('type') == SERVICE_INFO_CHAR_NAME:
                            value = characteristic.get('value', '')
                            return value
        return None

    def getId(self) -> str:
        return self.info['id']

    def getIpAddress(self) -> str:
        return self.info['address']

    def getName(self) -> str:
        return self.info['name'].split('._hap')[0]

    def getCategory(self) -> str:
        return self.info['category']

    def getRawInfo(self):
        return self.info

    def getFwVersion(self):
        return self.fwversion

    def _getSetupWord(self):
        word = HAADevice.getCustomCommand(self.getFwVersion())
        log.debug("FW {}-> {}".format(self.getFwVersion(),word))
        return word

    def _getWordToReboot(self):
        # here check version to change word
        return self._getSetupWord() + "2"

    def _getWordToEnterSetup(self):
        # here check version to change word
        return self._getSetupWord() + "1"

    def _getWordToWifiReconnection(self):
        # here check version to change word
        return self._getSetupWord() + "3"

    def _getWordToStartUpdate(self):
        # here check version to change word
        return self._getSetupWord() + "0"

    def dumpHomekitData(self):
        for accessory in self.data:
            aid = accessory['aid']
            for service in accessory['services']:
                s_type = service['type']
                s_iid = service['iid']
                print('{aid}.{iid}: #{stype}#'.format(aid=aid, iid=s_iid, stype=ServicesTypes.get_short(s_type)))

                for characteristic in service['characteristics']:
                    c_iid = characteristic['iid']
                    value = characteristic.get('value', '')
                    c_type = characteristic['type']
                    c_format = characteristic['format']
                    perms = ','.join(characteristic['perms'])
                    desc = characteristic.get('description', '')
                    c_type = CharacteristicsTypes.get_short(c_type)
                    print('  {aid}.{iid}: ({description}) #{ctype}# [{perms}]'.format(aid=aid,
                                                                                      iid=c_iid,
                                                                                      ctype=c_type,
                                                                                      perms=perms,
                                                                                      description=desc))
                    print('    Value: {value}'.format(value=value))

    def configReboot(self):
        characteristics = [(self.setupChar[0], self.setupChar[1], self._getWordToReboot())]
        results = self.pairing.put_characteristics(characteristics, do_conversion=True)

    def configEnterSetup(self):
        characteristics = [(self.setupChar[0], self.setupChar[1], self._getWordToEnterSetup())]
        results = self.pairing.put_characteristics(characteristics, do_conversion=True)

    def configStartUpdate(self):
        characteristics = [(self.setupChar[0], self.setupChar[1], self._getWordToStartUpdate())]
        results = self.pairing.put_characteristics(characteristics, do_conversion=True)

    def configWifiReconnection(self):
        characteristics = [(self.setupChar[0], self.setupChar[1], self._getWordToWifiReconnection())]
        results = self.pairing.put_characteristics(characteristics, do_conversion=True)

    @staticmethod
    def getCustomCommand(version :str) -> str:
        for key, value in CustomCommands.items():
            cmp = versionCompare(version, key)
            log.debug("comparing {},{} -> {}".format(version,key,cmp))
            if cmp >= 0:
                #version > key
                return value

        return CUSTOM_HAA_COMMAND   

    @staticmethod
    def getLastRelease() -> str:
        try:
        #https://api.github.com/repos/{owner}/{repo}/releases/latest
          response = requests.get("https://api.github.com/repos/RavenSystem/esp-homekit-devices/releases/latest")
          return response.json()["name"]
        except Exception as e:
          return ""

    @staticmethod
    def isInSetupMode(ip) -> bool:
        try:
            if ip != "":
                url = "http://{}:{}".format(ip,SETUP_PORT)
                status_code = urllib.request.urlopen(url,timeout=0.8).getcode()
                return status_code == 200
            else:
                return False
        except Exception as e:
            return False

class Context:
    __instance = None

    @staticmethod
    def get():
        """ Static access method. """
        if Context.__instance is None:
            Context()
        return Context.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if Context.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            Context.__instance = self
            Context.__instance.config = None
            Context.__instance.logger = None
            Context.__instance.timeout = None
            Context.__instance.discoveredDevices = []
            Context.__instance.pairingfile = None

    def discoverHAA(self, doPrint: bool = False) -> int:
        results = Controller.discover(Context.get().get_timeout_sec())
        for info in results:
            if info['md'].startswith(HAA_MANUFACTURER):
                # dev = HAADevice(info)
                self._addHAADevice(info)

        if doPrint:
            for d in Context.__instance.discoveredDevices:
                print("Name: {:20s} Ip: {:20s} Id: {:20s} Category: {:20s}".format(
                    d['name'].split('._hap')[0],
                    d['address'],
                    d['id'],
                    d['category']))
        return len(Context.__instance.discoveredDevices)

    def discoverHAAInSetupMode(self,ip4 = socket.gethostbyname(socket.gethostname())  ):

        target_ip = "{}/24".format(ip4)
        #  target_ip = "192.168.1.1/24".format(ip4)
        # IP Address for the destination
        # create ARP packet
        arp = ARP(pdst=target_ip)
        # create the Ether broadcast packet
        # ff:ff:ff:ff:ff:ff MAC address indicates broadcasting
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        # stack them
        packet = ether/arp

        result = srp(packet, timeout=3, verbose=0)[0]

        # a list of clients, we will fill this in the upcoming loop
        clients = []

        for sent, received in result:
            # for each response, append ip and mac address to `clients` list
            clients.append({'ip': received.psrc, 'mac': received.hwsrc})

        print("Devices in Setup Mode:")
        for client in clients:
            if HAADevice.isInSetupMode(client['ip']):
                url = "http://{}:4567".format(client['ip'])
                print("{:16}    Mac:{}    {}".format(client['ip'], client['mac'],url))

    def _addHAADevice(self, device):
        Context.__instance.discoveredDevices.append(device)

    def getDiscoveredHAADevices(self) -> []:
        return Context.__instance.discoveredDevices

    def getDiscovereHAADeviceByName(self, name: str):
        for d in Context.__instance.discoveredDevices:
            if d['name'].split('._hap')[0] == name:
                return d
        return None

    def getDiscovereHAADeviceById(self, id: str):
        for d in Context.__instance.discoveredDevices:
            if d['id'] == id:
                return d
        return None

    def get_logger(self) -> logging.Logger:
        return Context.__instance.logger

    def get_config(self) -> argparse.Namespace:
        return Context.__instance.config

    def get_timeout_sec(self) -> int:
        return Context.__instance.timeout

    def sighandler(self, signum, frame):
        print('\r\nYou pressed Ctrl+C! Game Over...')
        sys.exit(0)


def parseArguments(config: argparse.Namespace) -> None:
    #    print( config )
    ctx = Context.get()
    ctx.logger = logging.getLogger()
    ctx.timeout = config.timeout

    if config.exec == 'scan' and config.name:
        ctx.logger.error("scan mode and name are not allowed together")
        sys.exit(0)

    if config.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    if config.log:
        logging.basicConfig(filename=config.log[0],
                            filemode='w',
                            format='%(asctime)s,%(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=log_level)
        handler = RotatingFileHandler(config.log[0], maxBytes=FILELOGSIZE, backupCount=5)
        log.addHandler(handler)
    else:
        logging.basicConfig(format='%(asctime)s,%(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=log_level)


if __name__ == '__main__':

    unixsignal.signal(unixsignal.SIGINT, Context.get().sighandler)

    config = parser.parse_args()

    haaDevices = []

    parseArguments(config)

    log = Context.get().get_logger()

    log.info("Last release: {}".format( HAADevice.getLastRelease() ))


    log.info("Discovering HAA devices in the network...")
    devsNo = Context.get().discoverHAA(True)

    controller = Controller()
    try:
        controller.load_data(config.file)
    except Exception as e:
        logging.error(e, exc_info=True)
        sys.exit(-1)

    pair_devices = controller.get_pairings()
    log.info("Found {}/{} devices online..\r\n".format(devsNo,len(pair_devices)))

    if config.exec == 'scan':
        if devsNo!=len(pair_devices) :
            if not 'SUDO_UID' in os.environ.keys():
                print("WARNING!!for setup mode scanning feature,the script it requires sudo")
                sys.exit(1)
            else:
                Context.get().discoverHAAInSetupMode()
    else:
        ## Validate name of the device
        if config.name != ALL_DEVICES_WILDCARD:
            dev = Context.get().getDiscovereHAADeviceByName(config.name)
            if not dev:
                log.error('"{a}" is not a valid device name found online'.format(a=config.name))
                sys.exit(-1)

            deviceIsPaired : bool = False
            #we found the name onlne , is it paired? get its Paired ID
            for k,v  in pair_devices.items():
                if dev['id']  == v._get_pairing_data()['AccessoryPairingID'] :
                    deviceIsPaired = True
                    break

            if not deviceIsPaired :
                log.error('"{a}" is an online device but NOT Paired'.format(a=config.name))
                sys.exit(-1)
        #############

        doexit: bool = False
        for k, v in pair_devices.items():
            if config.name == ALL_DEVICES_WILDCARD or k == config.name:
                try:
                    data = v.list_accessories_and_characteristics()
                except Exception as e:
                    log.error("{} NOT online..!".format(k))
                    continue

                if doexit:
                    break

                for accessory in data:
                    for service in accessory['services']:
                        s_type = service['type']
                        if s_type == SERVICE_INFO_TYPE:
                            for characteristic in service['characteristics']:
                                if characteristic.get('type') == SERVICE_INFO_CHAR_NAME:
                                    name = characteristic.get('value', '')
                                    zeroConfDev = Context.get().getDiscovereHAADeviceByName(name)
                                    if Context.get().getDiscovereHAADeviceByName(name) is not None  :
                                        if config.name == ALL_DEVICES_WILDCARD or config.name == name :
                                            haaDev = HAADevice(zeroConfDev, data, v)
                                            log.info("haa device {} handled ...".format(name))
                                            haaDevices.append(haaDev)
                                            if config.name != ALL_DEVICES_WILDCARD:
                                                # break on first device found if not all are considered
                                                doexit = True
                                                break


        print("")
        log.info("{} Devices Match".format(len(haaDevices)))
        
        for hd in haaDevices:
            if config.exec == "reboot":
                log.info("REBOOT Device: {:20s} Id: {:20s} Ip: {:20s}".format(hd.getName(), hd.getId(), hd.getIpAddress()))
                hd.configReboot()
            elif config.exec == "update":
                log.info("UPDATE Device: {:20s} Id: {:20s} Ip: {:20s}".format(hd.getName(), hd.getId(), hd.getIpAddress()))
                log.info("use: nc -kulnw0 45678")
                hd.configStartUpdate()
            elif config.exec == "wifi":
                log.info("WIFI RECONNECTION Device: {:20s} Id: {:20s} Ip: {:20s}".format(hd.getName(), hd.getId(),
                                                                                         hd.getIpAddress()))
                hd.configWifiReconnection()
            elif config.exec == "setup":
                log.info("SETUP Device: {:20s} Id: {:20s} Ip: {:20s}".format(hd.getName(), hd.getId(), hd.getIpAddress()))
                log.info("http://{}:4567".format(hd.getIpAddress()))
                hd.configEnterSetup()
            elif config.exec == "dump":
                log.info("DUMP Device: {:20s} Id: {:20s} Ip: {:20s}".format(hd.getName(), hd.getId(), hd.getIpAddress()))
                hd.dumpHomekitData()
            elif config.exec == "version":
                log.info("Device: {:20s} Version: {:20s}".format(hd.getName(),hd.getFwVersion()))
