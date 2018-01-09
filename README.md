# ha-zha-new
=======

#### update of the zha component
based on the work from rcloran and others
Converted to a custom_component for an easier way to test and distribute to others without changing the homeassistant code. Should be forked back to the HA  codeafter testing. 

**I have the original Xiaomi sensors not the Aqara, but should work for these also**

**Current State:needs my bellows changes(timeout values and device_updated event)** 

## 1/8 dev-loader branch merged into master ->added support for:
- tradfri dimmable bulbs, not tested for the temperature bulbs, but maybe working
- loadable device handler modules in custom_components/device/
  - to parse attribute reports
  - to initalize endpoint based on model name
- template support, templates in device directoy
- auto detect xiaomi sensors, tested with the xiaomi original sensors, aqara should work,
  but attributes may not correct
- added pressure sensor, to  be tested

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



check out inside your $home/.homeassistant/ diretory, 

USAGE: 

```
#my current zha config with xiaomi sensors and tradfri bulbs
zha_new:
    usb_path: /dev/ttyUSB0
    database_path: /home/homeassistant/.homeassistant/zigbee.db
    device_config: 
  device_config: 
# tradfri dimmer
    "00:0b:57:ff:fe:24:18:9f-1":
      template: tradfri_dimmer
# tradfri dimmable bulbs
    "00:0b:57:ff:fe:2d:ab:35-1":
      template: TRADFRI_bulb
    "00:0b:57:ff:fe:b2:d3:b7-1":
      template: TRADFRI_bulb


     
