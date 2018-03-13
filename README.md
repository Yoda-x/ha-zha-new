# ha-zha-new
=======
## Breaking update
switched from old bellows to zigpy/zigpy and zigpy/bellows
Most of my needed changes are in the original zigpy distro. I will create PR´s for the others. For newer features or to be save use my bellows&zigpy fork.
### update of the zha component
based on the work from rcloran and others
Converted to a custom_component for an easier way to test and distribute to others without changing the homeassistant code. Should be forked back to the HA  codeafter testing. 


## NEW
- metering/on-off support for sitecom WLE-1000 plugs with reporting
- Aquara Water sensors as binary-sensors
- add RSSI/LQI information in entity attributes
- added zha_new object to monitor some parameters, which is helpful to see whats going on during pairing 
- - device left
- - permit enabled
- - device joined
- - device init - settting up device in hass
- - run - normal operations

## tested devices
- xiaomi and aquara sensors
- tradfri bulbs
- tradfri dimmer

## loadable device handler
create your own device handlers for unsupported devices, see files under custom_components/devices

## use master-pre-0,61 branch for HA <= 0.60 and master- >= 0.63
pre 0.61 code - no updates

## Todo
- detect returning endpoints and update state ( mainly for bulbs), needs endpoint 0 (zdo) enabled in zha Ha component



##USAGE:
check out inside your $home/.homeassistant/ directory, code needs to be in custom_component

**configuration example:**
tradfri bulbs and dimmer need  to use the template definition, xiaome sensors gets autodetected


    #my current zha config with xiaomi sensors and tradfri bulbs
    zha_new:
        usb_path: /dev/ttyUSB0
        database_path: /home/homeassistant/.homeassistant/zigbee.db
        device_config: 
    # tradfri dimmer
        "00:0b:57:ff:fe:24:18:9f-1":
          template: tradfri_dimmer
    # tradfri dimmable bulbs
        "00:0b:57:ff:fe:2d:ab:35-1":
          template: TRADFRI_bulb
        "00:0b:57:ff:fe:b2:d3:b7-1":
          template: TRADFRI_bulb

## History
## 1/8 dev-loader branch merged into master ->added support for:
- tradfri dimmable bulbs, not tested for the temperature bulbs, but maybe working
- loadable device handler modules in custom_components/device/
  - to parse attribute reports
  - to initalize endpoint based on model name
- template support, templates in device directoy
- auto detect xiaomi sensors, tested with the xiaomi original sensors, aqara work,  but some attributes are not correct ->TODO
- added pressure sensor, works for Aqara weather sensor -> TODO: need to separate original xiaomi and aquare templates

### Master branch
- device specific modules, get loaded based on model
- xiaomi battery and other attributes
- working Xiaomi Door/windows sensor as binary_sensor with state updates inside HA
- working Xiaomi HT sensors inside HA
- use in_cluster and out_cluster to override predefined cluster_profile from bellows, that not match non_standard devices
- configure reporting inside configuration.yaml
- working original xiaomi motion sensor, clear detection after 20 sec, as sensor only send detection reports, but no "clear" reports
- if a device leaves, the device gets removed from the database. Thus, you can unpair and pair a device now, without need to clear the database
- see the zha.yaml file for configuration
- it will create a base entity and a entity for each sensor(motion, temp, humidity, on/off)
