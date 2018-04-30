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
            "config_report": [
                [6, 0, 0, 1800, 1],
            ],
            "in_cluster": [0x0000, ],
            "type": "binary_sensor",
        }
    elif selector in ['lumi.sensor_ht', ] and self.endpoint_id == 1:
        config = {
            "config_report": [
                [0x0402, 0, 10, 600, 5],
                [0x0405, 0, 10, 600, 5],
            ],
            "in_cluster": [0x0000, ],
            "type": "sensor",
        }
    elif selector in ['lumi.weather', ] and self.endpoint_id == 1:
        config = {
            "config_report": [
                [0x0402, 0, 10, 120, 5],
                [0x0403, 0, 10, 120, 5],
                [0x0405, 0, 10, 120, 5],
            ],
            "in_cluster": [0x0000, ],
            "type": "sensor",
        }
    elif selector in ['lumi.sensor_motion', ]:
        config = {
            "config_report": [
                [0x0406, 0, 10, 1800, 1],
            ],
            "in_cluster": [0x0000, ],
            #       "type": "binary_sensor",
        }
    elif selector in ['lumi.sensor_motion.aq2', ]:
        config = {
            "config_report": [
                [0x0406, 0, 10, 1800, 1],
                [0x0400, 0, 10, 1800, 10],
            ],
            "in_cluster": [0x0000, ],
            #       "type": "binary_sensor",
        }
    elif selector == 'lumi.sensor_wleak.aq1':
        config = {
            "in_cluster": [0x0000, ],
            "type": "binary_sensor",
            "config_report": [
                [65281, 0, 10, 1800, 1],
            ]
        }

    node_config.update(config)


def _battery_percent(voltage):
    """calculate percentage."""
    min_voltage = 2750
    max_voltage = 3100
    return (voltage - min_voltage) / (max_voltage - min_voltage) * 100


def _parse_attribute(entity, attrib, value, *argv):
    """ parse non standard atrributes."""
    import bellows.types as t
    from zigpy.zcl import foundation as f

    if type(value) is str:
        result = bytearray()
        result.extend(map(ord, value))
        value = result

    if entity.entity_connect == {}:
        entity_store = zha_new.get_entity_store(entity.hass)
        device_store = entity_store.get(entity._endpoint._device._ieee, {})
        for dev_ent in device_store:
            if hasattr(dev_ent, 'cluster_key'):
                entity.entity_connect[dev_ent.cluster_key] = dev_ent

    attributes = {}
    if attrib == 0xff02:
        _LOGGER.debug("Parse type:%s", type(value))
        attribute_name = ("state", "battery_voltage_mV",
                          "val3", "val4",
                          "val5", "val6")
        result = []
        value = value[1:]
        while value:
            svalue, value = f.TypeValue.deserialize(value)
            result.append(svalue.value)
            _LOGGER.debug("parse 0xff02: %s", svalue.value)
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
            10: "X-attrib-10"
        }
        result = {}
        _LOGGER.debug("Parse dict 0xff01: parsing")
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
    if "battery_level" in attributes:
        entity._state = attributes.get("battery_level", 0)
    for attr in ("temperature", "humidity"):
        if attr in attributes and attr in entity.entity_connect:
            entity.entity_connect[attr]._state = attributes[attr]
    if "pressure" in attributes:
        entity.entity_connect["pressure"]._state = round(
            float(attributes["pressure"]) / 100, 1)

    attributes["Last seen"] = dt_util.now()
    entity._device_state_attributes.update(attributes)
    return(attrib, result)
