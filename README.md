# ha-zha-new
**update of the zha component**

based on the work from rcloran and others

Converted to a custom_component for an easier way to test and distribute to others without changing the homeassistant code. Should be forked back to the HA  codeafter testing. 

**Current State:needs my bellows changes** 
- working Xiaomi Door/windows sensor as binary_sensor with state updates inside HA
- working Xiaomi HT sensors inside HA
- use in_cluster and out_cluster to override predefined cluster_profile from bellows, that not match non_standard devices
- configure reporting inside configuration.yaml
- (dev) working original xiaomi motion sensor, clear detection after 20 sec, as sensor only send detection reports, but no "clear" reports
- (dev) if a device leaves, the device gets removed from the database. Thus, you can unpair and pair a device now, without need to clear the database
- see the zha.yaml file for configuration
- it will create a base entity and a entity for each sensor(motion, temp, humidity, on/off)



check out inside your $home/.homeassistant/ diretory, 

USAGE:

```
zha_new:
    usb_path: /dev/ttyUSB0
    database_path: /home/homeassistant/.homeassistant/zigbee.db
    device_config: 
# Door sensor
      "00:15:8d:00:01:d8:24:e0-1":
        type: binary_sensor
        in_cluster: [ 0, 25, 3,  0xffff ]
        out_cluster: [ 0, 3, 4, 5, 8, 6, 25]
        config_report:
          - [ 1, 20, 1, 1200, 10]
          - [ 6, 0, 1, 120, '01']
# HT sensor    
      "00:15:8d:00:01:6f:fa:50-1":
        type: sensor
        config_report:
          - [ 0x0405, 0, 1, 120, 5]
          - [ 0x0402, 0, 1, 120, 5]
```
     
