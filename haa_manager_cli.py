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
import base64
import aiohomekit
import requests
import socket, os
import signal as unixsignal
from logging.handlers import RotatingFileHandler
import configargparse
import urllib.request
from scapy.all import ARP, Ether, srp
import socket
import requests
from concurrent.futures import ThreadPoolExecutor
import argparse
import asyncio
from collections.abc import AsyncIterator
import contextlib
import logging
import sys
import re
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf
from aiohomekit.zeroconf import ZeroconfServiceListener
from aiohomekit import Controller
from aiohomekit.model.categories import Categories


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
HAA_CUSTOM_ADVANCED_CONFIG_CHAR = "F0000103-0218-2017-81BF-AF2B7C833922"
SETUP_PORT = 4567

# GitHub repository information
REPO_OWNER = "RavenSystem"
REPO_NAME = "esp-homekit-devices"
HEADER_FILE_PATH = "HAA/HAA_Main/main/header.h"

ALL_DEVICES_WILDCARD = "*"

FILELOGSIZE = 1024 * 1024 * 10  # 10 mb max




# GitHub related functions
def get_all_tags(debug=False):
    """
    Fetch and print all tags from the GitHub repository using pagination.
    """
    per_page = 100
    page = 1
    tags = []

    print("🔎 Fetching tags from GitHub...")

    while True:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/tags?per_page={per_page}&page={page}"
        if debug:
            print(f"[DEBUG] Requesting: {url}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            page_tags = [tag["name"] for tag in data]
            tags.extend(page_tags)

            if debug:
                print(f"[DEBUG] Page {page}: {len(page_tags)} tag(s)")

            page += 1
        except requests.RequestException as e:
            print(f"❌ Error fetching tags: {e}")
            break

    print(f"✅ Found {len(tags)} total tag(s):")
    for tag in tags:
        print(f"  • {tag}")

    return tags

def get_latest_release(debug=False):
    """
    Fetch and return the latest release tag from GitHub.
    """
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    if debug:
        print(f"[DEBUG] Requesting latest release from: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        tag_name = data.get("tag_name")
        if tag_name:
            print(f"✅ Latest release tag: {tag_name}")
            return tag_name
        else:
            print("⚠️ No tag_name found in latest release.")
            return None
    except requests.RequestException as e:
        print(f"❌ Error fetching latest release: {e}")
        return None

def get_custom_haa_command(version_tag="master", debug=False):
    """
    Retrieve the CUSTOM_HAA_COMMAND value from header.h for the given tag.
    """
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{version_tag}/{HEADER_FILE_PATH}"

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Error fetching header file: {e}")
        return None

    content = response.text

    if debug:
        print(f"\n📥 Fetching header file from: {url}")
        print("[DEBUG] First 5 lines of header file:")
        for line in content.splitlines()[:5]:
            print(f"  {line}")

    match = re.search(r'#define\s+CUSTOM_HAA_COMMAND\s+"([^"]+)"', content)

    if match:
        command = match.group(1)
        print(f"✅ CUSTOM_HAA_COMMAND found: \"{command}\"")
        return command
    else:
        print("⚠️ CUSTOM_HAA_COMMAND not found.")
        return None


parser = configargparse.ArgParser(default_config_files=[''])
parser.add("-l", "--log", nargs=1, metavar=("log File"), default=False,
           help=" path file to save log")  # this option can be set in a config file because it starts with '--'
parser.add('-v', action='version', version=VERSION + "\n" + AUTHOR)
parser.add('-d', '--debug', action='store_true', default=False, help='debug mode')
parser.add('-t', '--timeout', required=False, type=int, default=10, help='Number of seconds to wait')
parser.add('-f', action='store', required=False, dest='file', help='File with the pairing data')
parser.add('-i', action='store', required=False, dest='id', default=ALL_DEVICES_WILDCARD, help='pairID of device found online,shown on scan. wildcard "*" means all')

subparsers = parser.add_subparsers(dest='command', required=True, help="Commands to execute")

script_parser = subparsers.add_parser('script', help="Run a script action")
script_parser.add_argument('params', nargs=argparse.REMAINDER, help="Parameters for the script")

update_parser = subparsers.add_parser('update', help="Update action")
reboot_parser = subparsers.add_parser('reboot', help="Reboot action")
setup_parser = subparsers.add_parser('setup', help="Setup action")
wifi_parser = subparsers.add_parser('wifi', help="WiFi action")
dump_parser = subparsers.add_parser('dump', help="Dump action")
scan_parser = subparsers.add_parser('scan', help="Scan action")
version_parser = subparsers.add_parser('version', help="Get version action")

# Add new subparsers for GitHub-related commands
tags_parser = subparsers.add_parser('tags', help="List all available GitHub tags")
custom_parser = subparsers.add_parser('custom', help="Get CUSTOM_HAA_COMMAND value from a tag or version")
custom_parser.add_argument('--tag', help="GitHub tag or branch (default: master)")
custom_parser.add_argument('--version', help="HAA version (e.g., 12.14.6)")
latest_parser = subparsers.add_parser('latest', help="Get the latest GitHub release tag")


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # Connessione fittizia a Google DNS
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"  # Fallback in caso di errore

def homekitCategoryToString(category : int) -> str :
    if category == Categories.OTHER :
        return "Other"
    if category == Categories.BRIDGE:
        return "Bridge"
    if category == Categories.FAN:
        return "Fan"
    if category == Categories.GARAGE:
        return "Garage"
    if category == Categories.LIGHTBULB:
        return "LightBulb"
    if category == Categories.DOOR_LOCK:
        return "Door Lock"
    if category == Categories.OUTLET:
        return "Outlet"
    if category == Categories.SWITCH:
        return "Switch"
    if category == Categories.THERMOSTAT:
        return "Thermostat"
    if category == Categories.SENSOR:
        return "Sensor"
    if category == Categories.SECURITY_SYSTEM:
        return "Security System"
    if category == Categories.DOOR:
        return "Door"
    if category == Categories.WINDOW:
        return "Window"
    if category == Categories.WINDOW_COVERING:
        return "Window Covering"
    if category == Categories.PROGRAMMABLE_SWITCH:
        return "Programmable Switch"
    if category == Categories.RANGE_EXTENDER:
        return "Range Extender"
    if category == Categories.IP_CAMERA:
        return "Ip Camera"
    if category == Categories.VIDEO_DOOR_BELL:
        return "Video DoorBell"
    if category == Categories.AIR_PURIFIER:
        return "Air Purifier"
    if category == Categories.HEATER:
        return "Heater"
    if category == Categories.AIR_CONDITIONER:
        return "Air Conditioner"
    if category == Categories.HUMIDIFIER:
        return "Humidifier"
    if category == Categories.DEHUMIDIFER:
        return "Dehumidifier"
    if category == Categories.APPLE_TV:
        return "Apple Tv"
    if category == Categories.HOMEPOD:
        return "Homepod"
    if category == Categories.SPEAKER:
        return "Speaker"
    if category == Categories.AIRPORT:
        return "Airport"
    if category == Categories.SPRINKLER:
        return "Sprinkler"
    if category == Categories.FAUCET:
        return "Faucet"
    if category == Categories.SHOWER_HEAD:
        return "Shower Head"
    if category == Categories.TELEVISION:
        return "Television"
    if category == Categories.REMOTE:
        return "Remote"
    if category == Categories.ROUTER:
        return "Router"
    return "Unknown Category"


# versiontuple("2.3.1") > versiontuple("10.1.1") -> False
def versiontuple(v):
    return tuple(map(int, (v.split("."))))

# Method to compare two versions.
# Return 1 if v2 is smaller,
# -1 if v1 is smaller,
# 0 if equal
def versionCompare(v1, v2):
    if versiontuple(v2) < versiontuple(v1):
       return 1
    if versiontuple(v1) < versiontuple(v2):
       return -1
    if versiontuple(v1) == versiontuple(v2):
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
        self.advsetupChar = self._getAdvancedCustomSetupService()
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

    def _getAdvancedCustomSetupService(self):
        for accessory in self.data:
            aid = accessory['aid']
            for service in accessory['services']:
                s_type = service['type']
                s_iid = service['iid']
                if s_type == HAA_CUSTOM_SERVICE:
                    for characteristic in service['characteristics']:
                        if characteristic.get('type') == HAA_CUSTOM_ADVANCED_CONFIG_CHAR:
                            value = characteristic.get('value', '')
                            # 'aid': 1, 'iid': 65012,
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
        return self.info.description.id

    def getIpAddress(self) -> str:
        return self.info.description.addresses[0]

    def getName(self) -> str:
        return self.info.description.name.split('._hap')[0]

    def getCategory(self) -> str:
        return self.info.description.category

    def getRawInfo(self):
        return self.info

    def getFwVersion(self):
        return self.fwversion

    def _getSetupWord(self):
        word = HAADevice.getCustomCommand(self.getFwVersion())
        Context.get().get_logger().debug("FW {}-> {}".format(self.getFwVersion(), word))
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

    def _getWordToReadScript(self):
        # here check version to change word
        str = self._getSetupWord() + "01 "  # with extra space necessary!
        enc = base64.b64encode(str.encode("utf-8"))
        return enc.decode('utf-8')

    def dumpHomekitData(self):
        for accessory in self.data:
            aid = accessory['aid']
            for service in accessory['services']:
                s_type = service['type']
                s_iid = service['iid']
                print('{aid}.{iid}: #{stype}#'.format(aid=aid, iid=s_iid, stype=s_type))

                for characteristic in service['characteristics']:
                    c_iid = characteristic['iid']
                    value = characteristic.get('value', '')
                    c_type = characteristic['type']
                    c_format = characteristic['format']
                    perms = ','.join(characteristic['perms'])
                    desc = characteristic.get('description', '')

                    print('  {aid}.{iid}: ({description}) #{ctype}# [{perms}]'.format(aid=aid,
                                                                                      iid=c_iid,
                                                                                      ctype=c_type,
                                                                                      perms=perms,
                                                                                      description=desc))
                    print('    Value: {value}'.format(value=value))

    async def configReboot(self):
        characteristics = [(self.setupChar[0], self.setupChar[1], self._getWordToReboot())]
        results = await self.pairing.put_characteristics(characteristics)

    async def configEnterSetup(self):
        characteristics = [(self.setupChar[0], self.setupChar[1], self._getWordToEnterSetup())]
        results = await self.pairing.put_characteristics(characteristics)

    async def configStartUpdate(self):
        characteristics = [(self.setupChar[0], self.setupChar[1], self._getWordToStartUpdate())]
        results = await self.pairing.put_characteristics(characteristics)

    async def configWifiReconnection(self):
        characteristics = [(self.setupChar[0], self.setupChar[1], self._getWordToWifiReconnection())]
        results = await self.pairing.put_characteristics(characteristics)

    async def getConfigScript(self):
        if not self.advsetupChar:
            return None
        characteristics = [(self.advsetupChar[0], self.advsetupChar[1], self._getWordToReadScript())]
        results = await self.pairing.put_characteristics(characteristics)
        results = await self.pairing.get_characteristics([(self.advsetupChar[0], self.advsetupChar[1])])
        script = results.get((self.advsetupChar[0], self.advsetupChar[1]), {}).get('value', None)
        if script:
            return base64.b64decode(script).decode("utf-8")
        else:
            return None

    @staticmethod
    def getCustomCommand(version: str) -> str:
        """
        Get custom command for a specific HAA version.
        First checks local mapping, then tries to fetch from GitHub if not found.
        """
    
        # If not found in dictionary, try to fetch from GitHub
        try:
            # Create a tag name based on version
            tag_name = f"HAA_{version}"
            # Try to get the command from GitHub
            command = get_custom_haa_command(tag_name, False)
            if command:
                return command
            else:
                # If specific version tag not found, try with master
                command = get_custom_haa_command("master", False)
                if command:
                    return command
        except Exception as e:
            Context.get().get_logger().error(f"Error getting command from GitHub: {e}")
            sys.exit(-1)
            
        # Fallback to default command
        return CUSTOM_HAA_COMMAND

    @staticmethod
    def getLastRelease() -> str:
        try:
            tag = get_latest_release(False)
            if tag:
                return tag
            else:
                # Fallback to original method
                response = requests.get("https://api.github.com/repos/RavenSystem/esp-homekit-devices/releases/latest")
                return response.json()["name"]
        except Exception as e:
            return ""

    @staticmethod
    def isInSetupMode(ip) -> bool:
        try:
            if ip != "":
                url = "http://{}:{}".format(ip, SETUP_PORT)
                status_code = urllib.request.urlopen(url, timeout=0.8).getcode()
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
            Context.__instance.zeroConf = AsyncZeroconf()
            Context.__instance.controller = aiohomekit.Controller(async_zeroconf_instance=Context.__instance.zeroConf)

    def load_data(self, file):
        try:
            Context.__instance.controller.load_data(file)
            return Context.__instance.controller.pairings
        except Exception:
            raise SystemExit

    @contextlib.asynccontextmanager
    async def get_controller(self) -> AsyncIterator[Controller]:
        zeroconf = AsyncZeroconf()

        controller = Controller(
            async_zeroconf_instance=zeroconf
        )

        async with zeroconf:
            listener = ZeroconfServiceListener()
            browser = AsyncServiceBrowser(
                zeroconf.zeroconf,
                [
                    "_hap._tcp.local.",
                    "_hap._udp.local.",
                ],
                listener=listener,
            )

            async with controller:
                yield controller

            await browser.async_cancel()

    async def discoverHAA(self, doPrint: bool = False) -> int:
        async with self.get_controller() as controller:
            self.controller = controller
            await asyncio.sleep(self.get_timeout_sec())

            async for discovery in controller.async_discover(self.get_timeout_sec()):
                desc = discovery.description

                if desc.model.startswith(HAA_MANUFACTURER):
                    self._addHAADevice(discovery)

        if doPrint:
            for d in Context.__instance.discoveredDevices:
                print("PairId: {:20s} Ip: {:20s} Name: {:20s} Category: {:20s}".format(
                    d.description.id,
                    d.description.addresses[0],
                    d.description.name.split('._hap')[0],
                    homekitCategoryToString(d.description.category)))

        return len(Context.__instance.discoveredDevices)

    def discoverHAAInSetupMode(self, ip4=None):
        if not ip4:
            ip4 = get_local_ip()
        Context.get().get_logger().debug(f"My IP: {ip4}")
        base_ip = ".".join(ip4.split(".")[:3])  # Es: "192.168.1.1" -> "192.168.1"
        timeout = 0.8

        def scan_ip(ip):
            try:
                with socket.create_connection((ip, SETUP_PORT), timeout):
                    return ip  # LETS CONSIDER IN setup mode if connection is ok
            except (socket.timeout, socket.error):
                return None

        ip_range = [f"{base_ip}.{i}" for i in range(1, 255)]
        devices_in_setup = []

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = executor.map(scan_ip, ip_range)

        for ip in results:
            if ip:
                devices_in_setup.append(ip)

        print("Devices in Setup Mode:")
        for device_ip in devices_in_setup:
            url = f"http://{device_ip}:4567"
            print(f"{device_ip:16} URL: {url}")

    def _addHAADevice(self, device):
        Context.__instance.discoveredDevices.append(device)

    def getDiscoveredHAADevices(self) -> []:
        return Context.__instance.discoveredDevices

    def getDiscovereHAADeviceByName(self, name: str):
        for d in Context.__instance.discoveredDevices:
            if d.description.name.split('._hap')[0] == name:
                return d
        return None

    def getDiscovereHAADeviceById(self, id: str):
        for d in Context.__instance.discoveredDevices:
            if d.description.id == id:
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
    ctx = Context.get()
    ctx.logger = logging.getLogger()
    ctx.timeout = config.timeout

    if config.command == 'scan' and config.id and config.id != ALL_DEVICES_WILDCARD:
        ctx.logger.error("scan mode and ID are not allowed together")
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
        ctx.logger.addHandler(handler)
    else:
        logging.basicConfig(format='%(asctime)s,%(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=log_level)


def getOnlineDevs(pair_devices, discoveredDevices):
    devs = {}
    for disc in discoveredDevices:
        for k, v in pair_devices.items():
            if disc.description.id == k:
                devs[str(k)] = v
    return devs


async def main(argv: list[str] | None = None) -> None:
    unixsignal.signal(unixsignal.SIGINT, Context.get().sighandler)

    config = parser.parse_args()

    parseArguments(config)

    log = Context.get().get_logger()

    # Handle GitHub-related commands first
    if config.command == 'tags':
        get_all_tags(config.debug)
        return
    elif config.command == 'latest':
        get_latest_release(config.debug)
        return
    elif config.command == 'custom':
        if config.version:
            # If version provided, check custom command for that version
            tag_name = f"HAA_{config.version}"
            print(f"🔍 Looking up CUSTOM_HAA_COMMAND for version: {config.version} (tag: {tag_name})")
            command = HAADevice.getCustomCommand(config.version)
            print(f"Custom command for version {config.version}: {command}")
        elif config.tag:
            # If tag provided, lookup directly with that tag
            print(f"🔍 Looking up CUSTOM_HAA_COMMAND for tag: {config.tag}")
            get_custom_haa_command(config.tag, config.debug)
        else:
            # Default to master
            print("🔍 Looking up CUSTOM_HAA_COMMAND for latest master")
            get_custom_haa_command("master", config.debug)
        return

    # For device commands, check if -f is provided
    if not config.file:
        log.error("File with pairing data is required for this command")
        sys.exit(1)

    haaDevices = []

    log.info("Last release: {}".format(HAADevice.getLastRelease()))

    log.info("Discovering HAA devices in the network...")

    devsNo = await Context.get().discoverHAA(True)

    pair_devices = Context.get().load_data(config.file)

    onlineDevs = getOnlineDevs(pair_devices, Context.get().getDiscoveredHAADevices())

    log.info("Found {} devices online. {} paired {} are Online\r\n".format(devsNo, len(pair_devices), len(onlineDevs)))

    if config.command == 'scan':
        Context.get().discoverHAAInSetupMode()
    else:
        ## Validate name of the device
        if config.id != ALL_DEVICES_WILDCARD:
            dev = Context.get().getDiscovereHAADeviceById(config.id)
            if not dev:
                log.error('"{a}" is not a valid device name found online'.format(a=config.id))
                sys.exit(-1)

            deviceIsPaired : bool = False
            #we found the name onlne , is it paired? get its Paired ID
            for k,v in pair_devices.items():
                if dev.description.id == k:#v._pairing_data.get('AccessoryPairingID') :
                    deviceIsPaired = True
                    break

            if not deviceIsPaired:
                log.error('"{a}" is an online device but NOT Paired'.format(a=config.id))
                sys.exit(-1)
        #############

        doexit: bool = False
        for k, v in onlineDevs.items(): #pair_devices.items():
            if config.id == ALL_DEVICES_WILDCARD or k == config.id:

                try:
                    data = await v.list_accessories_and_characteristics()
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
                                    zeroConfDev = Context.get().getDiscovereHAADeviceById(k)
                                    if Context.get().getDiscovereHAADeviceById(k) is not None:
                                        if config.id == ALL_DEVICES_WILDCARD or config.id == zeroConfDev.description.id:
                                            haaDev = HAADevice(zeroConfDev, data, v)
                                            log.info("haa device {} ({}) handled ...".format(k,name))
                                            haaDevices.append(haaDev)
                                            if config.id != ALL_DEVICES_WILDCARD:
                                                # break on first device found if not all are considered
                                                doexit = True
                                                break

        print("")
        log.info("{} Devices Match".format(len(haaDevices)))

        for hd in haaDevices:
            if config.command == "reboot":
                log.info("REBOOT Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(),hd.getName(), hd.getId(), hd.getIpAddress()))
                await hd.configReboot()
            elif config.command == "update":
                log.info("UPDATE Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(),hd.getName(), hd.getId(), hd.getIpAddress()))
                log.info("use: nc -kulnw0 45678")
                await hd.configStartUpdate()
            elif config.command == "wifi":
                log.info("WIFI RECONNECTION Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(),hd.getName(), hd.getId(),
                                                                                         hd.getIpAddress()))
                await hd.configWifiReconnection()
            elif config.command == "setup":
                log.info("SETUP Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(),hd.getName(), hd.getId(), hd.getIpAddress()))
                log.info("http://{}:4567".format(hd.getIpAddress()))
                await hd.configEnterSetup()
            elif config.command == "dump":
                log.info("DUMP Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(),hd.getName(), hd.getId(), hd.getIpAddress()))
                hd.dumpHomekitData()
            elif config.command == "script":
                if config.params:
                     print(f"Running script with parameters: {config.params}")
                else:
                    log.info("Script Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(),hd.getName(), hd.getId(), hd.getIpAddress()))
                    script = await hd.getConfigScript()
                    print(script)
                    print()
            elif config.command == "version":
                log.info("Device: {}({})       Version: {:20s}".format(hd.getId(),hd.getName(),hd.getFwVersion()))
            

def sync_main():
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
        sync_main()
