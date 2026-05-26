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
import subprocess
import aiohomekit
import requests
import socket, os
import signal as unixsignal
from logging.handlers import RotatingFileHandler
import configargparse
import urllib.request
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
from zeroconf import InterfaceChoice
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf, AsyncServiceInfo
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
           help=" path file to save log")
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
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

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


# ---------------------------------------------------------------------------
# HAP discovery helpers — bypass aiohomekit's broken async_discover()
# ---------------------------------------------------------------------------

class _RawHAPListener:
    """Zeroconf listener that only records (type, name) tuples without any I/O."""
    def __init__(self):
        self.pending = []

    def add_service(self, zc, type_, name):
        logging.getLogger().debug("[mDNS] add_service  type=%s  name=%s", type_, name)
        self.pending.append((type_, name))

    def remove_service(self, zc, type_, name):
        logging.getLogger().debug("[mDNS] remove_service  name=%s", name)
        self.pending = [(t, n) for t, n in self.pending if n != name]

    def update_service(self, zc, type_, name):
        logging.getLogger().debug("[mDNS] update_service  name=%s", name)
        if (type_, name) not in self.pending:
            self.pending.append((type_, name))


class _HAPInfo:
    """Mirrors the fields that HAADevice expects on discovery.description."""
    def __init__(self, info: AsyncServiceInfo, props: dict):
        self.id = props.get('id', '').lower()
        self.model = props.get('md', '')
        self.name = info.name          # full mDNS name, e.g. "MyDev._hap._tcp.local."
        self.addresses = info.parsed_addresses()
        try:
            self.category = Categories(int(props.get('ci', 0)))
        except Exception:
            self.category = Categories.OTHER


class _HAPDiscovery:
    """Thin wrapper so callers can use discovery.description.xxx."""
    def __init__(self, info: AsyncServiceInfo, props: dict):
        self.description = _HAPInfo(info, props)


class _PairingInfo:
    """Fallback description built from aiohomekit pairing data when mDNS has no TXT."""
    def __init__(self, pairing_id: str, pairing):
        self.id = pairing_id
        self.model = ''
        self.name = pairing_id  # no mDNS name available
        self.category = Categories.OTHER
        pd = getattr(pairing, '_pairing_data', {})
        addr = pd.get('AccessoryIP', pd.get('AccessoryAddress', pd.get('Address', None)))
        if addr is None:
            self.addresses = []
        elif isinstance(addr, list):
            self.addresses = addr
        else:
            self.addresses = [addr]


class _PairingDiscovery:
    """Used when a pairing exists but the device was not found via mDNS."""
    def __init__(self, pairing_id: str, pairing):
        self.description = _PairingInfo(pairing_id, pairing)


# ---------------------------------------------------------------------------


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
        addrs = self.info.description.addresses
        return addrs[0] if addrs else 'unknown'

    def getName(self) -> str:
        # Prefer HomeKit name from accessories data; fall back to mDNS service name
        if self.name:
            return self.name
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
        return self._getSetupWord() + "2"

    def _getWordToEnterSetup(self):
        return self._getSetupWord() + "1"

    def _getWordToWifiReconnection(self):
        return self._getSetupWord() + "3"

    def _getWordToStartUpdate(self):
        return self._getSetupWord() + "0"

    def _getWordToReadScript(self):
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
        try:
            tag_name = f"HAA_{version}"
            command = get_custom_haa_command(tag_name, False)
            if command:
                return command
            else:
                command = get_custom_haa_command("master", False)
                if command:
                    return command
        except Exception as e:
            Context.get().get_logger().error(f"Error getting command from GitHub: {e}")
            sys.exit(-1)

        return CUSTOM_HAA_COMMAND

    @staticmethod
    def getLastRelease() -> str:
        try:
            tag = get_latest_release(False)
            if tag:
                return tag
            else:
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
            Context.__instance.zeroConf = None
            Context.__instance.controller = None
            Context.__instance._hap_listener = None

    def load_data(self, file):
        try:
            Context.__instance.controller.load_data(file)
            return Context.__instance.controller.pairings
        except Exception:
            raise SystemExit

    @contextlib.asynccontextmanager
    async def get_controller(self) -> AsyncIterator[Controller]:
        # Bind to all interfaces so we receive mDNS on every NIC (eth0, wlan0, …)
        zeroconf = AsyncZeroconf(interfaces=InterfaceChoice.All)
        controller = Controller(async_zeroconf_instance=zeroconf)
        listener = _RawHAPListener()

        async with zeroconf:
            browser = AsyncServiceBrowser(
                zeroconf.zeroconf,
                [
                    "_hap._tcp.local.",
                    "_hap._udp.local.",
                ],
                listener=listener,
            )
            async with controller:
                self.zeroConf = zeroconf
                self.controller = controller
                self._hap_listener = listener
                yield controller
            await browser.async_cancel()

    async def discoverHAA(self, doPrint: bool = False) -> int:
        log = self.get_logger()

        # Wait for mDNS browser to collect service announcements
        log.debug("[disc] sleeping %ds for mDNS...", self.get_timeout_sec())
        await asyncio.sleep(self.get_timeout_sec())

        pending = list(self._hap_listener.pending)
        log.debug("[disc] mDNS listener collected %d service(s)", len(pending))
        if not pending:
            print("[disc] WARNING: mDNS browser found 0 HAP services. "
                  "Check that the Pi is on the same network/VLAN as the devices "
                  "and that mDNS/Bonjour is not blocked by a firewall or router.")

        for type_, name in pending:
            log.debug("[disc] resolving: %s", name)
            try:
                info = AsyncServiceInfo(type_, name)
                ok = await info.async_request(self.zeroConf.zeroconf, 3000)
                if not ok:
                    log.debug("[disc] async_request timeout for %s", name)
                    continue
                props = {
                    (k.decode() if isinstance(k, bytes) else k):
                    (v.decode() if isinstance(v, bytes) else str(v) if v is not None else '')
                    for k, v in (info.properties or {}).items()
                }
                model = props.get('md', '')
                addrs = info.parsed_addresses()
                log.debug("[disc] %s  md='%s'  addrs=%s", name, model, addrs)
                # Accept if model matches OR if name starts with "HAA-" (empty md during boot)
                short_name = name.split('._hap')[0]
                if model.startswith(HAA_MANUFACTURER) or (not model and short_name.upper().startswith('HAA-')):
                    self._addHAADevice(_HAPDiscovery(info, props))
                else:
                    log.debug("[disc] skip (not HAA): %s  md='%s'", name, model)
            except Exception as e:
                log.debug("[disc] error resolving %s: %s", name, e)

        log.debug("[disc] HAA devices found: %d", len(Context.__instance.discoveredDevices))

        if doPrint:
            for d in Context.__instance.discoveredDevices:
                print("PairId: {:20s} Ip: {:20s} Name: {:20s} Category: {:20s}".format(
                    d.description.id,
                    d.description.addresses[0] if d.description.addresses else 'N/A',
                    d.description.name.split('._hap')[0],
                    homekitCategoryToString(d.description.category)))

        return len(Context.__instance.discoveredDevices)

    def discoverHAAInSetupMode(self, ip4=None):
        if not ip4:
            ip4 = get_local_ip()
        Context.get().get_logger().debug(f"My IP: {ip4}")
        base_ip = ".".join(ip4.split(".")[:3])
        timeout = 0.8

        def scan_ip(ip):
            try:
                with socket.create_connection((ip, SETUP_PORT), timeout):
                    return ip
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

    # Suppress spurious aiohomekit background-task errors (AccessoryDisconnectedError
    # from _process_config_changed): they don't affect our logic.
    logging.getLogger().addFilter(_SuppressAiohomekitBgErrors())


def getOnlineDevs(pair_devices, discoveredDevices):
    devs = {}
    for disc in discoveredDevices:
        for k, v in pair_devices.items():
            if disc.description.id == k:
                devs[str(k)] = v
    return devs


class _SuppressAiohomekitBgErrors(logging.Filter):
    """Filter out spurious aiohomekit background-task AccessoryDisconnectedError noise."""
    def filter(self, record):
        if record.levelno == logging.ERROR and 'Failure running background task' in record.getMessage():
            return False
        return True


def _read_arp_cache(log) -> dict:
    """Read OS ARP cache from /proc/net/arp. Returns dict: MAC (lowercase) -> IP."""
    mac_to_ip = {}
    try:
        with open('/proc/net/arp', 'r') as f:
            next(f)  # skip header line
            for line in f:
                parts = line.split()
                if len(parts) >= 4:
                    ip = parts[0]
                    mac = parts[3].lower()
                    if mac != '00:00:00:00:00:00':
                        mac_to_ip[mac] = ip
        log.debug("ARP cache: %d entries", len(mac_to_ip))
    except Exception as e:
        log.debug("ARP cache read error: %s", e)
    return mac_to_ip


def _load_friendly_names(pairing_file: str) -> dict:
    """Read pairing JSON. Returns dict: lowercase AccessoryPairingID -> friendly name (e.g. HAA-07AA1F)."""
    import json
    result = {}
    try:
        with open(pairing_file) as f:
            raw = json.load(f)
        for name, data in raw.items():
            if isinstance(data, dict):
                pid = data.get('AccessoryPairingID', '').lower()
                if pid:
                    result[pid] = name
    except Exception:
        pass
    return result


def _prescan_and_patch(pairing_file: str, log) -> tuple:
    """
    Read the pairing JSON, nmap-scan for HAP ports, ARP-match device MACs,
    write a patched temp JSON with correct IPs so aiohomekit always reads
    the right IP from disk — not a stale cached value.
    Returns: (patched_file_path, {AccessoryPairingID_lower -> ip})
    Falls back to (original_file, {}) on any error.
    """
    import json as _json, tempfile, os as _os
    try:
        import nmap as nmap_lib
    except ImportError:
        log.debug("python-nmap not installed (pip install python-nmap)")
        return pairing_file, {}

    try:
        with open(pairing_file) as f:
            raw = _json.load(f)
    except Exception as e:
        log.debug("prescan: cannot read pairing file: %s", e)
        return pairing_file, {}

    # Collect HAP ports directly from the raw JSON
    ports_set = set()
    for json_key, data in raw.items():
        if isinstance(data, dict):
            port = data.get('AccessoryPort')
            if port:
                ports_set.add(int(port))

    if not ports_set:
        log.debug("prescan: no AccessoryPort found")
        return pairing_file, {}

    local_ip = get_local_ip()
    subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
    ports_csv = ",".join(str(p) for p in sorted(ports_set))
    log.info("nmap: scanning %s  ports [%s] ...", subnet, ports_csv)

    try:
        nm = nmap_lib.PortScanner()
        nm.scan(hosts=subnet, ports=ports_csv, arguments='-sT -T4 --open')
    except Exception as e:
        log.debug("nmap scan error: %s", e)
        return pairing_file, {}

    nmap_ips: set = set()
    for host in nm.all_hosts():
        if 'tcp' in nm[host]:
            for pdata in nm[host]['tcp'].values():
                if pdata['state'] == 'open':
                    nmap_ips.add(host)

    log.info("nmap: found %d host(s) with HAP port(s) open", len(nmap_ips))

    # nmap TCP connects populate the OS ARP cache — read it now
    arp_cache = _read_arp_cache(log)
    arp_cache = {mac: ip for mac, ip in arp_cache.items() if ip in nmap_ips}
    log.debug("ARP cache filtered to nmap IPs: %d entries", len(arp_cache))

    # MAC suffix matching: JSON key "HAA-07AA1F" → last 6 hex → match ARP MAC.
    # HAA device names encode the last 3 WiFi MAC bytes: HAA-07AA1F <-> xx:xx:xx:07:aa:1f
    json_name_to_ip: dict = {}   # JSON top-level key  -> ip
    pid_info: dict = {}          # AccessoryPairingID (lower) -> {'ip', 'name', 'mac'}

    for json_key, data in raw.items():
        if not isinstance(data, dict):
            continue
        suffix = json_key.split('-')[-1].lower()   # "07aa1f" from "HAA-07AA1F"
        if len(suffix) != 6:
            continue
        for mac, ip in arp_cache.items():
            if mac.replace(':', '').endswith(suffix):
                json_name_to_ip[json_key] = ip
                pid = data.get('AccessoryPairingID', '').lower()
                if pid:
                    pid_info[pid] = {'ip': ip, 'name': json_key, 'mac': mac}
                log.info("ARP match: %-20s  %s  (via %s)", json_key, ip, mac)
                break

    unmatched = [n for n in raw if isinstance(raw[n], dict) and n not in json_name_to_ip]
    if unmatched:
        log.info("No ARP match for: %s", ", ".join(sorted(unmatched)))

    if not json_name_to_ip:
        return pairing_file, {}

    # Build patched JSON: update ALL address-like keys for matched devices
    patched = {}
    for json_key, data in raw.items():
        if not isinstance(data, dict) or json_key not in json_name_to_ip:
            patched[json_key] = data
            continue
        ip = json_name_to_ip[json_key]
        entry = dict(data)
        for key, val in list(entry.items()):
            if any(x in key.lower() for x in ('ip', 'address', 'host', 'addr')):
                entry[key] = [ip] if isinstance(val, list) else ip
        entry.setdefault('AccessoryIP', ip)
        patched[json_key] = entry

    fd, tmp_path = tempfile.mkstemp(suffix='.json', prefix='haa_pairing_')
    with _os.fdopen(fd, 'w') as f:
        _json.dump(patched, f)

    log.debug("prescan: patched pairing JSON -> %s", tmp_path)
    return tmp_path, pid_info


def _reset_pairing_connection(pairing) -> None:
    """
    Clear aiohomekit's cached connection so the next call opens a fresh TCP session.
    Bridge sub-accessories share the bridge IP; after a failed attempt on the wrong IP
    the cached (broken) connection must be cleared before trying a new IP.
    """
    for attr in ('_connection', '_impl', '_session', '_transport'):
        try:
            current = getattr(pairing, attr, None)
            if current is not None:
                close_fn = getattr(current, 'close', None)
                if close_fn and not asyncio.iscoroutinefunction(close_fn):
                    try:
                        close_fn()
                    except Exception:
                        pass
                try:
                    setattr(pairing, attr, None)
                except (AttributeError, TypeError):
                    pass
        except Exception:
            pass


async def _try_connect_pairing(k: str, v, name_to_ip: dict, ctx, log):
    """
    HAP connection for one pairing.
    IP is already correct in the pairing object: _prescan_and_patch wrote it
    into the JSON before aiohomekit loaded it.
    Returns (k, v, zc_dev, data) or None.
    """
    dev_info = name_to_ip.get(k)
    if not dev_info:
        log.debug("%s: no ARP match — skipping", k)
        return None

    arp_ip = dev_info['ip']
    log.debug("%s (%s): trying %s", dev_info['name'], k, arp_ip)
    _reset_pairing_connection(v)
    try:
        data = await asyncio.wait_for(v.list_accessories_and_characteristics(), timeout=5.0)
        zc = ctx.getDiscovereHAADeviceById(k) or _PairingDiscovery(k, v)
        return (k, v, zc, data)
    except Exception as e:
        log.debug("%s (%s): failed -> %s: %s", dev_info['name'], arp_ip, type(e).__name__, e)

    log.debug("%s NOT online (IP: %s)", dev_info['name'], arp_ip)
    return None


async def _run_device_command(config, log) -> None:
    """Runs all device-related commands inside a single controller context."""
    ctx = Context.get()

    log.info("Last release: {}".format(HAADevice.getLastRelease()))

    # Pre-scan BEFORE aiohomekit loads the pairings: patch the JSON with correct IPs
    # so aiohomekit reads the right IP from disk, not a stale cached value.
    patched_file, name_to_ip = await asyncio.to_thread(_prescan_and_patch, config.file, log)
    try:
      async with ctx.get_controller():
        pair_devices = ctx.load_data(patched_file)

        if config.command == 'scan':
            ctx.discoverHAAInSetupMode()
            return

        if config.id != ALL_DEVICES_WILDCARD and config.id not in pair_devices:
            log.error('"{}" is not a known paired device'.format(config.id))
            sys.exit(-1)

        candidates = {
            k: v for k, v in pair_devices.items()
            if config.id == ALL_DEVICES_WILDCARD or k == config.id
        }

        total = len(candidates)
        results = []
        for i, (k, v) in enumerate(candidates.items(), 1):
            dev_info = name_to_ip.get(k)
            if dev_info:
                desc = f"{dev_info['name']}  {dev_info['ip']}  {dev_info['mac']}"
            else:
                desc = f"{k}  (no match)"
            print(f"\rConnecting ({i}/{total}): {desc}...", end='\033[K', flush=True)
            result = await _try_connect_pairing(k, v, name_to_ip, ctx, log)
            results.append(result)
        print()  # newline after progress

        haaDevices = []
        for result in results:
            if result is None:
                continue
            k, v, zc, data = result
            for accessory in data:
                for service in accessory['services']:
                    if service['type'] != SERVICE_INFO_TYPE:
                        continue
                    for char in service['characteristics']:
                        if char.get('type') == SERVICE_INFO_CHAR_NAME:
                            device_name = char.get('value', '')
                            haaDev = HAADevice(zc, data, v)
                            if haaDev.manufacturer and haaDev.manufacturer.startswith(HAA_MANUFACTURER):
                                log.debug("haa device {} ({}) handled ...".format(k, device_name))
                                haaDevices.append(haaDev)
                            break
                    break

        print("")
        log.info("{} Devices Match".format(len(haaDevices)))

        # Emit PairId lines so external parsers (e.g. HA push script) can extract
        # ip, mac, name, category without needing mDNS discovery.
        for hd in haaDevices:
            print("PairId: {:20s} Ip: {:20s} Name: {:20s} Category: {:20s}".format(
                hd.getId(),
                hd.getIpAddress(),
                hd.getName(),
                homekitCategoryToString(hd.getCategory())))

        for hd in haaDevices:
            if config.command == "reboot":
                log.info("REBOOT Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(), hd.getName(), hd.getId(), hd.getIpAddress()))
                await hd.configReboot()
            elif config.command == "update":
                device_fw = hd.getFwVersion()
                latest_tag = HAADevice.getLastRelease()

                latest_ver = None
                if latest_tag:
                    m = re.search(r'(\d+(?:\.\d+)+)', str(latest_tag))
                    latest_ver = m.group(1) if m else latest_tag

                needs_update = True
                if device_fw and latest_ver:
                    try:
                        same_version = (versionCompare(device_fw, latest_ver) == 0)
                        needs_update = not same_version
                    except Exception:
                        needs_update = (device_fw != latest_ver)

                if needs_update:
                    log.info("UPDATE Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(), hd.getName(), hd.getId(), hd.getIpAddress()))
                    log.info("Device fw: {} -> Latest release: {}".format(device_fw, latest_tag))
                    log.info("use: nc -kulnw0 45678")
                    await hd.configStartUpdate()
                else:
                    log.info("SKIP UPDATE: Device {} ({}) already at latest version {}".format(hd.getId(), hd.getName(), device_fw))
            elif config.command == "wifi":
                log.info("WIFI RECONNECTION Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(), hd.getName(), hd.getId(), hd.getIpAddress()))
                await hd.configWifiReconnection()
            elif config.command == "setup":
                log.info("SETUP Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(), hd.getName(), hd.getId(), hd.getIpAddress()))
                log.info("http://{}:4567".format(hd.getIpAddress()))
                await hd.configEnterSetup()
            elif config.command == "dump":
                log.info("DUMP Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(), hd.getName(), hd.getId(), hd.getIpAddress()))
                hd.dumpHomekitData()
            elif config.command == "script":
                if config.params:
                    print(f"Running script with parameters: {config.params}")
                else:
                    log.info("Script Device: {}({})        Id: {:20s} Ip: {:20s}".format(hd.getId(), hd.getName(), hd.getId(), hd.getIpAddress()))
                    script = await hd.getConfigScript()
                    print(script)
                    print()
            elif config.command == "version":
                log.info("Device: {}({})       Version: {:20s}".format(hd.getId(), hd.getName(), hd.getFwVersion()))
    finally:
        if patched_file != config.file:
            try:
                os.unlink(patched_file)
            except Exception:
                pass


async def main(argv: list[str] | None = None) -> None:
    unixsignal.signal(unixsignal.SIGINT, Context.get().sighandler)

    config = parser.parse_args()

    parseArguments(config)

    log = Context.get().get_logger()

    # Handle GitHub-related commands first (no network discovery needed)
    if config.command == 'tags':
        get_all_tags(config.debug)
        return
    elif config.command == 'latest':
        get_latest_release(config.debug)
        return
    elif config.command == 'custom':
        if config.version:
            tag_name = f"HAA_{config.version}"
            print(f"🔍 Looking up CUSTOM_HAA_COMMAND for version: {config.version} (tag: {tag_name})")
            command = HAADevice.getCustomCommand(config.version)
            print(f"Custom command for version {config.version}: {command}")
        elif config.tag:
            print(f"🔍 Looking up CUSTOM_HAA_COMMAND for tag: {config.tag}")
            get_custom_haa_command(config.tag, config.debug)
        else:
            print("🔍 Looking up CUSTOM_HAA_COMMAND for latest master")
            get_custom_haa_command("master", config.debug)
        return

    # For device commands, -f is required
    if not config.file:
        log.error("File with pairing data is required for this command")
        sys.exit(1)

    await _run_device_command(config, log)


def sync_main():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    sync_main()
