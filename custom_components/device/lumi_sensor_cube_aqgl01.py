"""" custom py file for device Aqara Cube."""
import logging
import homeassistant.util.dt as dt_util
from custom_components import zha_new

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'cube_event'


def _custom_endpoint_init(self, node_config, *argv):
    """set node_config based on Lumi device_type."""
    config = {}
    selector = node_config.get('template', None)
    _LOGGER.debug(" selector: %s", selector)
    if not selector:
        selector = argv[0]
        _LOGGER.debug(" selector: %s", selector)
    if selector in ['lumi_sensor_cube', 'lumi_sensor_cube_aqgl01'] and self.endpoint_id == 1:
        config = {
            "in_cluster": [0x0000, 0x0003, 0x0012, 0x0019],
            "out_cluster": [0x0000, 0x0003, 0x0004, 0x0005, 0x0012, 0x00019],
            "type": "sensor",
        }
    elif selector in ['lumi_sensor_cube', 'lumi_sensor_cube_aqgl01'] and self.endpoint_id == 2:
        config = {
            "config_report": [
                [0x0012, 85, 60, 3600, 5],
            ],
            "in_cluster": [0x0003, 0x0012],
            "out_cluster": [0x0003, 0x0004, 0x0005, 0x0012],
            "type": "sensor",
        }
        self.add_input_cluster(0x0012)
    elif selector in ['lumi_sensor_cube', 'lumi_sensor_cube_aqgl01'] and self.endpoint_id == 3:
        config = {
            "config_report": [
                [0x000c, 85, 60, 3600, 5],
                [0x000c, 65285, 60, 3600, 5],
            ],
            "in_cluster": [0x0003, 0x000c],
            "out_cluster": [0x0003, 0x0004, 0x0005, 0x000c],
            "type": "sensor",
        }
        self.add_input_cluster(0x000c)
    node_config.update(config)


def _parse_attribute(entity, attrib, value, *argv):
    """ parse non standard atrributes."""
    import zigpy.types as t
    from zigpy.zcl import foundation as f
    _LOGGER.debug('parse value type %s', type(value))
    result = []
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
    if attrib == 85:
        attributes["value"] = float(t.Double(value))
        attributes["last seen"] = dt_util.now()
        if isinstance(value, float):       # rotation
            event = "rotation"
            command = 'cube_rotation'
        else:
            if value >= 499:
                event = "double_tap"
            elif value >= 250:
                event = "slide"
            elif value >= 100:
                event = "flip_180"
            elif value == 0:
                event = "shake"
            elif value <= 15:
                event = "noise"
            elif value > 0:
                event = "flip_90"
            command = 'cube_slide'
        _LOGGER.debug("value### "+str(result) + "## state ## "+event)
        entity._state = event
        event_data = {
                    'entity_id': entity.entity_id,
                    'channel': 'Level',
                    'command': command,
                    'step': event
                   }
        entity.hass.bus.fire('cube_event', event_data)
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

    if "path" in attributes:
        entity._endpoint._device.handle_RouteRecord(attributes["path"])
    entity._device_state_attributes.update(attributes)


return(attrib, result)
