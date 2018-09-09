"""" custom py file for device."""
import logging
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


def _custom_endpoint_init(self, node_config, *argv):
    config = {
         "in_cluster": [0x0000, ],
         "out_cluster": [0x0006], 
        "type": "binary_sensor",
        }
    node_config.update(config)
    self.add_output_cluster(6)

def _parse_attribute(entity, attrib, value, *argv, **kwargs):
    """ parse non standard atrributes."""
    import zigpy.types as t
    from zigpy.zcl import foundation as f
    _LOGGER.debug('parse %s %s %a %s', attrib, value, argv, kwargs)

    attributes = {}

    if attrib == 0xff01:
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
    else:
        result = value
    _LOGGER.debug("Parse Result: after else")

    attributes["Last seen"] = dt_util.now()
    if "path" in attributes:
        self._entity._endpoint._device.handle_RouteRecord(attributes["path"])
    entity._device_state_attributes.update(attributes)
    if (kwargs['cluster_id'] == 6) and (attrib == 0) and (result == 1):
        event_data = {
        'entity_id': entity.entity_id,
        'channel': "OnOff",
        'type': 'toggle',
        }
        entity.hass.bus.fire('click', event_data)
    entity_state = entity._state ^ 1
    return(attrib, result)

