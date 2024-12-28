# HAA Manager CLI

  
The simplest solution to handle [HAA](https://github.com/RavenSystem/esp-homekit-devices) devices in Home Assistant is to add extra pairing in HAA Setup mode adding them to ios controller besides HA : In this way you can use HAA Manager App in parallel to Home Assistant.(That's the way I suggest you).

For those who don't want extra pairing there is HAA Manager CLI.


# How to Install
 
HAA Manager CLI needs some sudo privileges for some features (scan network i.e).
It's not mandatory, is up to you.

`pip install -r requirements.txt`

or

`sudo pip install -r requirements.txt`


# Get Pairing Data From Home Assistant

HAA Manager CLI needs pairing data to work.You can find these info in 

`HA_CONFIG_FOLDER/.storage/core.config_entries`

you must copy them and create a pairing-file.json in the form:

```
{
        "alias1": {
          "AccessoryPairingID": "xx:xx:xx:xx:xx:xx",
          "AccessoryLTPK": "xxxxxxxxxxxxxxxxxxxxxxxxx",
          "iOSPairingId": "xxxxxxxxxxxxxxxx",
          "iOSDeviceLTSK": "xxxxxxxxxxxxxxxxxx",
          "iOSDeviceLTPK": "xxxxxxxxxxxxxxxxxxxxxx",
          "AccessoryIP": "192.168.1.77",
          "AccessoryPort": 5556,
          "Connection": "IP"
        },
        "alias2": {
          "AccessoryPairingID": "xx:xx:xx:xx:xx:xx",
          "AccessoryLTPK": "xxxxxxxxxxxxxxxxxxxxxxxxx",
          "iOSPairingId": "xxxxxxxxxxxxxxxx",
          "iOSDeviceLTSK": "xxxxxxxxxxxxxxxxxx",
          "iOSDeviceLTPK": "xxxxxxxxxxxxxxxxxxxxxx",
          "AccessoryIP": "192.168.1.77",
          "AccessoryPort": 5556,
          "Connection": "IP"
        }
}
```

alias1..alias2 etc are only aliases for the devices : give them different names for each item.


# Commands
There are 8 commands available : update , reboot , enter setup mode , reconnecting WIFI , dump all data device ,scan, get device FW version , get script.

```
usage: haa_manager_cli.py [-h] [-l log File] [-v] [-d] [-t TIMEOUT] -f FILE [-i ID] {script,update,reboot,setup,wifi,dump,scan,version} ...

positional arguments:
  {script,update,reboot,setup,wifi,dump,scan,version}
                        Commands to execute
    script              Run a script action
    update              Update action
    reboot              Reboot action
    setup               Setup action
    wifi                WiFi action
    dump                Dump action
    scan                Scan action
    version             get version action

options:
  -h, --help            show this help message and exit
  -l log File, --log log File
                        path file to save log
  -v                    show program's version number and exit
  -d, --debug           debug mode
  -t TIMEOUT, --timeout TIMEOUT
                        Number of seconds to wait
  -f FILE               File with the pairing data
  -i ID                 pairID of device found online,shown on scan. wildcard "*" means all

```

# Scan

Scan Mode allows to discover devices (already paired in Home Assistant) in your network.

`sudo python haa_manager_cli.py -f pairing-file.json scan`


```
INFO Discovering HAA devices in the network..

PairId: 1F:27:12:BA:BF:xx      Name: HAA-AABBCC       Ip: 192.168.1.151           Category: Window Covering  
PairId: 6B:D5:81:BD:5B:yy      Name: HAA-786678       Ip: 192.168.1.51            Category: Switch    
20:26:27,INFO Found 2/2 devices online..

Devices in Setup Mode:
```

You can also see if any device (from your pairing file) is in Setup Mode.

# Update

For all operations you must use the name discovered with the scan.

`python haa_manager_cli.py -f pairing-file.json -i 1F:27:12:BA:BC:58 update`

```
INFO Discovering HAA devices in the network..
PairId: 1F:27:12:BA:BC:58       Name: HAA-AABBCC       Ip: 192.168.1.151          Category: Window Covering  
PairId: 6B:D5:81:BD:5B:EA       Name: HAA-786678       Ip: 192.168.1.51           Category: Switch 
20:32:55,INFO Found 8/9 devices online..

20:33:09,ERROR HAA-12345 NOT online..!
20:33:10,INFO 1 Devices Match
20:33:10,INFO UPDATE Device: HAA-AABBCC        Id: 1F:27:12:BA:BC:58    Ip: 192.168.1.151
20:33:10,INFO use: nc -kulnw0 45678
```

20:33:09,ERROR HAA-12345 NOT online..! means that in the paring file there is the device BUT it's not online during the scan.

To see the update progress , as suggested , use:

`nc -kulnw0 45678`

# Set All devices together

If you need to setup all devices together is possible to use "*" as a wildcard.
For example to update all devices in the network:

`python haa_manager_cli.py -f pairing-file.json -i "*" update`




# Donations

If you like the project , consider a donation

<a href="https://www.paypal.com/donate/?business=HDH35MSZ6VW58&no_recurring=0&currency_code=EUR" 
target="_blank">
<img src="https://www.paypalobjects.com/en_US/GB/i/btn/btn_donateCC_LG.gif" alt="PayPal this" 
title="PayPal – The safer, easier way to pay online!" border="0" />
</a>
