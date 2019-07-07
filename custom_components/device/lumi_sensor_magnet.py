"""" custom py file for device."""
import logging
import homeassistant.util.dt as dt_util
from custom_components import zha_new

_LOGGER = logging.getLogger(__name__)

def _custom_endpoint_init(self, node_config, *argv):
    """set node_config based obn Lumi device_type."""
    config = {}
    selector = node_config.get('template', None)
    if not selector:
        selector = argv[0]
        _LOGGER.debug(" selector: %s", selector)
    if selector in ['lumi.sensor_magnet', 'lumi.sensor_magnet.aq2']:
        config = {
            "in_cluster": [0x0000, 0x0006],
            "type": "binary_sensor",
        }
        self.add_input_cluster(0x0006)

    elif selector in ['lumi.sensor_ht', ] and self.endpoint_id == 1:
        config = {
            'primary_cluster': 0x0405, 
            "config_report": [
                [0x0402, 0, 10, 600, 5],
                [0x0405, 0, 10, 600, 5],
            ],
            "in_cluster": [0x0000, 0x0402, ],  # just use one sensor as main
            "out_cluster": [],
            "type": "sensor",
        }
        self.add_input_cluster(0x0402)
        self.add_input_cluster(0x0405)

    elif selector in ['lumi.weather', ] and self.endpoint_id == 1:
        config = {
            "config_report": [
                [0x0402, 0, 10, 120, 5],
                [0x0403, 0, 10, 120, 5],
                [0x0405, 0, 10, 120, 5],
            ],
            "in_cluster": [0x0000, 0x0402],  # just use one sensor as main
            "out_cluster": [],
            "type": "sensor",
        }
        self.add_input_cluster(0x0402)
        self.add_input_cluster(0x0403)
        self.add_input_cluster(0x0405)
    elif selector in ['lumi.sensor_motion', ]:
        config = {
            "config_report": [
                [0x0406, 0, 10, 1800, 1],
            ],
            "in_cluster": [0x0000, 0xffff, 0x0406],
            "out_cluster": [],
            "type": "binary_sensor",
        }
        self.add_input_cluster(0x0406) # cluster_not in endpoint clusters 
    elif selector in ['lumi.sensor_motion.aq2', ]:
        config = {
            'primary_cluster': 0x406,
            "config_report": [
                [0x0406, 0, 10, 1800, 1],
                [0x0400, 0, 10, 1800, 10],
            ],
            "in_cluster": [0x0000, 0x0406,  0xffff],
            "out_cluster": [],
            #            "type": "binary_sensor",
        }
        self.add_input_cluster(0x0406)
        self.add_input_cluster(0x0400)
    elif selector == 'lumi.sensor_wleak.aq1':
        config = {
            "in_cluster": [0x0000, 0xff01, 0x0500],
            "out_cluster": [0x0500],
            "type": "binary_sensor",
            "config_report": [
                [0xff01, 0, 10, 1800, 1],
            ],
        }
        self.add_input_cluster(0x0500)
        self.add_output_cluster(0x0500)
    elif selector == 'lumi.vibration.aq1' and self.endpoint_id == 1:
        config = {
            "type": "binary_sensor",
            "in_cluster": [0x0000, 0x0101]
        }
#        asyncio.ensure_future(zha_new.discover_cluster_values(self, self.in_clusters[0x0101]))
    node_config.update(config)


def _battery_percent(voltage):
    """calculate percentage."""
    min_voltage = 2750
    max_voltage = 3100
    return (voltage - min_voltage) / (max_voltage - min_voltage) * 100


def _parse_attribute(entity, attrib, value, *argv, **kwargs):
    """ parse non standard atrributes."""
    import zigpy.types as t
    from zigpy.zcl import foundation as f
    _LOGGER.debug('parse %s %s %a %s', attrib, value, argv, kwargs)
#    if type(value) is str:
#        result = bytearray()
#        result.extend(map(ord, value))
#        value = result

    if entity.entity_connect == {}:
        entity_store = zha_new.get_entity_store(entity.hass)
        device_store = entity_store.get(entity._endpoint._device._ieee, {})
        for dev_ent in device_store:
            if hasattr(dev_ent, 'cluster_key'):
                entity.entity_connect[dev_ent.cluster_key] = dev_ent

    attributes = {}
    if attrib == 0xff02:
#        _LOGGER.debug("Parse dict 0xff02: set friendly attribute names")
        attribute_name = ("state", "battery_voltage_mV",
                          "val3", "val4",
                          "val5", "val6")
        result = []
        for svalue in value:
            result.append(svalue.value)
        attributes = dict(zip(attribute_name, result))

        if "battery_voltage_mV" in attributes:
            attributes["battery_level"] = int(
                _battery_percent(attributes["battery_voltage_mV"]))

    elif attrib == 0xff01:
        _LOGGER.debug("Parse dict 0xff01: set friendly attribute names")
        attribute_name = {
            4: "X-attrib-4",
            1: "battery_voltage_mV",
            100: "temperature",
            101: "humidity",
            102: "pressure",
            5: "X-attrib-5",
            6: "X-attrib-6",
            10: "path"  # was X-attrib-10
        }
        result = {}
        while value:
            skey = int(value[0])
            svalue, value = f.TypeValue.deserialize(value[1:])
            result[skey] = svalue.value
        for item, value in result.items():
            key = attribute_name[item] \
                if item in attribute_name else "0xff01-" + str(item)
            attributes[key] = value
        if "battery_voltage_mV" in attributes:
            attributes["battery_level"] = int(
                _battery_percent(attributes["battery_voltage_mV"]))
    elif attrib == 43041:
        attribute_name = ("X-attrib-val1",
                          "X-attrib-val2",
                          "X-attrib-val3")
        result = []
        svalue, value = t.uint40_t.deserialize(value)
        result.append(svalue)
        svalue, value = f.TypeValue.deserialize(value)
        result.append(svalue.value)
        svalue, value = f.TypeValue.deserialize(value)
        result.append(svalue.value)
        attributes = dict(zip(attribute_name, result))
    else:
        result = value
    _LOGGER.debug("Parse Result: %s", result)
    for attr in ("temperature", "humidity"):
        if attr in attributes and attr in entity.entity_connect:
            entity.entity_connect[attr]._state = attributes[attr]
    if "pressure" in attributes:
        entity.entity_connect["pressure"]._state = round(
            float(attributes["pressure"]) / 100, 0)

    attributes["last seen"] = dt_util.now()
    if "path" in attributes:
        entity._endpoint._device.handle_RouteRecord(attributes["path"])

    if entity._model == 'lumi.vibration.aq1':
        if attrib == 85:
            event_data = {
                    'entity_id': entity.entity_id,
                    'channel':  "alarm",
                    'type':  "vibration" if value == 1 else ("tilt" if value == 2 else "drop")
                   }
            entity.hass.bus.fire('alarm', event_data)
            attributes['alarm'] = event_data['type']
        elif attrib == 1283:
            _LOGGER.debug("Rotation: %s",  value)
            attributes['rotation'] = value
        elif attrib == 1288:
            angle_z = value & 0x0fff
            if angle_z > 2048:
                angle_z -= 4096
            angle_y = (value >> 16) & 0x0fff
            if angle_y > 2048:
                angle_y -= 4096
            angle_x = (value >> 32) & 0x0fff
            if angle_x > 2048:
                angle_x -= 4096
            _LOGGER.debug("Attrib 0x%04x: 0x%04x : %s %s %s",  attrib,  value,  angle_x,  angle_y,  angle_z)
            attributes['angle_x'] = angle_x
            attributes['angle_y'] = angle_y
            attributes['angle_z'] = angle_z
    elif entity._model in ['lumi.sensor_magnet.aq2', 'lumi.sensor_wleak.aq1']:
        if "temperature" in attributes:
            entity._state = attributes["temperature"]

    entity._device_state_attributes.update(attributes)
    return(attrib, result)
