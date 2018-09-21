"""" custom py file for device."""
import logging
import asyncio
import homeassistant.util.dt as dt_util
from custom_components import zha_new
import zigpy.types as t
_LOGGER = logging.getLogger(__name__)


def _custom_endpoint_init(self, node_config, *argv):
    """set node_config based obn Lumi device_type."""
    config = {}
    selector = node_config.get('template', None)
    if not selector:
        selector = argv[0]
    _LOGGER.debug(" selector: %s", selector)
    config = {
            "config_report": [
                [0xfc02, 0x0010, 1, 1800, t.uint8_t(1), 0x1241],
                [0xfc02, 0x0012, 1, 1800, t.uint16_t(1), 0x1241],
                [0xfc02, 0x0013, 1, 1800, t.uint16_t(1), 0x1241],
                [0xfc02, 0x0014, 1, 1800, t.uint16_t(1), 0x1241],
            ],
            "in_cluster": [0x0000, 0x0402, 0x0500, 0xfc02 ],
            "out_cluster": [],
            "type": "binary_sensor",
    }
    node_config.update(config)


def _parse_attribute(entity, attrib, value, *argv, **kwargs):
    """ parse non standard atrributes."""
    import zigpy.types as t
    from zigpy.zcl import foundation as f
    _LOGGER.debug('parse %s %s %a %s', attrib, value, argv, kwargs)
    cluster_id = kwargs.get('cluster_id',None)
    attributes = dict()
    if entity.entity_connect == {}:
        entity_store = zha_new.get_entity_store(entity.hass)
        device_store = entity_store.get(entity._endpoint._device._ieee, {})
        for dev_ent in device_store:
            if hasattr(dev_ent, 'cluster_key'):
                entity.entity_connect[dev_ent.cluster_key] = dev_ent
    if cluster_id == 0x0402:
        if attrib == 0:
           attributes['Temperature'] = value
    elif cluster_id == 0xfc02:
        if attrib == 0x0010:
            type = "move" 
        elif attrib == 0x0012:
            type = "X-Axis"
        elif attrib == 0x0013:
            type = "Y-Axis"
        elif attrib == 0x0014:
            type = "Z-Axis"
        attributes['last alarm'] = dt_util.now()
        event_data = {
                    'entity_id': entity.entity_id,
                    'channel': "alarm",
                    'type': type,
                    'value': value,
                   }
        entity.hass.bus.fire('alarm', event_data)
    entity._device_state_attributes.update(attributes)
    return(attrib, result)
