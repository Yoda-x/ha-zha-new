# ha-zha-new
**update of the zha component**

based on the work from rcloran and others

Converted to a custom_component for an easier way to test and distribute to others without changing the homeassistant code. Should be forked back to the HA  codeafter testing. 

**Current State:**
- working Xiaomi Door/windows sensor as binary_sensor with state updates inside HA
- use in_cluster and out_cluster to override predefined cluster_profile from bellows, that not match non_standard devices



check out inside your $home/.homeassistant/ diretory, 

USAGE:

```
zha_new:
    usb_path: /dev/ttyUSB0
    database_path: /home/homeassistant/.homeassistant/zigbee.db
    device_config: 
      "00:15:8d:00:01:d8:24:e0-1":
        type: binary_sensor
        in_cluster: [ 0, 25, 3, 6]
        out_cluster: [ 0, 3, 4, 5, 8, 6, 25]
      "00:15:8d:00:01:a4:e1:62-1":
        type: binary_sensor 
        in_cluster: [ 0, 25, 3, 6]
        out_cluster: [ 0, 3, 4, 5, 8, 6, 25]
```
     
