"""" custom py file for device."""
import logging
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


def _custom_endpoint_init(self, node_config, *argv):
    selector = node_config.get('template', None)
    if not selector:
        selector = argv[0]
        _LOGGER.debug(" selector: %s", selector)
    
    config = {
                 'type': 'binary_sensor',
            }
    self.add_input_cluster(0x0006)
    
    node_config.update(config)


def _parse_attribute(entity, attrib, value, *argv, **kwargs):
    """ parse non standard atrributes."""
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

#    if "path" in attributes:
#        self._entity._endpoint._device.handle_RouteRecord(attributes["path"])
    
    if (kwargs['cluster_id'] == 0x0006) and (attrib == 0x0000):
        event_data = {
            'entity_id': entity.entity_id,
            'channel': "MultiStateInput",
        }
        if result == 0:
            event_data['data'] = 'hold'
        elif result == 255:
            event_data['data'] = 'release'
        elif result == 1:
            event_data['data'] = 'single'
        elif result == 2:
            event_data['data'] = 'double'
        elif result == 3:
            event_data['data'] = 'tripple'
        elif result == 4:
            event_data['data'] = 'quad'
        elif result == 16:
            event_data['data'] = 'hold'
        elif result == 17:
            event_data['data'] = 'long_released'
        elif result == 18:
            event_data['data'] = 'shake'
        entity.hass.bus.fire('click', event_data)

    attributes["last seen"] = dt_util.now()
    entity._device_state_attributes.update(attributes)
    _LOGGER.debug('updated Attributes:%s', attributes)
    return(attrib, result)


def _battery_percent(voltage):
    """calculate percentage."""
    min_voltage = 2750
    max_voltage = 3100
    return (voltage - min_voltage) / (max_voltage - min_voltage) * 100
