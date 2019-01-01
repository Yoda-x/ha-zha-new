"""" custom py file for device."""
import logging
import asyncio
import homeassistant.util.dt as dt_util
from custom_components import zha_new

_LOGGER = logging.getLogger(__name__)


def _custom_endpoint_init(self, node_config, *argv):
    """set node_config based on Lumi device_type."""
    config = {}
    selector = node_config.get('template', None)
    if not selector:
        selector = argv[0]
    if self.endpoint_id == 1:
        config = {
            "in_cluster": [0x0000, 0x0006 ],
            "type": "switch",
        }
        node_config.update(config)
    elif self._endpoint_id == 2:
        config = {
            "config_report": [
                [0x000c, 0x0055, 0, 1800, 5],
            ], 
            "in_cluster": [0x0000, 0x000c], 
            "out_cluster": [], 
            "type": "sensor",
        }
        self.add_input_cluster(0x000c)
        node_config.update(config)


def _parse_attribute(entity, attrib, value, *argv, **kwargs):
    """parse non standard attributes."""
    import zigpy.types as t
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
    if attrib == 85:
        #result = []
        result = float(t.Double(value))
        attributes["power"] = float(t.Double(value))
        attributes["unit_of_measurement"] = 'W'
        attrib = 0
    else:
        result = value
    attributes["Last seen"] = dt_util.now()
    if "path" in attributes:
        entity._endpoint._device.handle_RouteRecord(attributes["path"])
    entity._device_state_attributes.update(attributes)
    return(attrib, result)
